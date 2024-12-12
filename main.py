import os
import time
import threading
import requests
import json
import logging
import random
from datetime import datetime, timedelta, UTC
import google.generativeai as genai
import signal
import sys
from typing import Optional, Dict, List, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bsky_bot.log'),
        logging.StreamHandler()
    ]
)

class BskyAINewsBot:
    def __init__(self, handle: str, app_password: str):
        self.handle = handle
        self.app_password = app_password
        self.access_token = None
        self.did = None
        self.base_url = "https://bsky.social/xrpc"
        self.running = True
        self.last_article = None
        self.last_checked_notification = datetime.now(UTC)
        
        # Prompt templates for varied posts
        self.post_prompts = [
            "Write a creative post about AI innovation. Discuss emerging trends and practical tips.",
            "Share insights about how AI is transforming various industries. Keep it concise and engaging.",
            "Explore the potential of AI in solving real-world problems. Provide a unique perspective.",
            "Discuss the latest breakthroughs in artificial intelligence. Make it interesting and under 280 characters."
        ]
        
        # Configure APIs
                # Add API key for GEMINI and NEWS API
        self.news_api_key = os.getenv('NEWS_API_KEY')
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # AI topics to track
        self.ai_topics = [
            'Claude', 'GPT-4', 'ChatGPT', 'Gemini', 'Copilot', 'Grok',
            'Anthropic', 'OpenAI', 'Microsoft', 'Google', 'xAI',
            'AI regulation', 'AI ethics', 'machine learning'
        ]

    def authenticate(self) -> None:
        """Authenticate with Bluesky."""
        try:
            response = requests.post(
                f"{self.base_url}/com.atproto.server.createSession",
                json={"identifier": self.handle, "password": self.app_password}
            )
            response.raise_for_status()
            data = response.json()
            self.access_token = data["accessJwt"]
            self.did = data["did"]
            logging.info("Authenticated with Bluesky")
        except Exception as e:
            logging.error(f"Authentication failed: {str(e)}")
            raise

    def create_post(self, text: str, reply_to: Optional[Dict] = None) -> Optional[str]:
        """Create a post or reply."""
        try:
            if not self.access_token:
                self.authenticate()

            post_data = {
                "$type": "app.bsky.feed.post",
                "text": text,
                "createdAt": datetime.now(UTC).isoformat().replace('+00:00', 'Z'),
                "langs": ["en"]
            }

            # Add reply reference if this is a reply
            if reply_to:
                post_data["reply"] = {
                    "root": {
                        "uri": reply_to["uri"],
                        "cid": reply_to["cid"]
                    },
                    "parent": {
                        "uri": reply_to["uri"],
                        "cid": reply_to["cid"]
                    }
                }

            response = requests.post(
                f"{self.base_url}/com.atproto.repo.createRecord",
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={
                    "repo": self.did,
                    "collection": "app.bsky.feed.post",
                    "record": post_data
                }
            )
            response.raise_for_status()
            return response.json().get("uri")
        except Exception as e:
            logging.error(f"Post creation error: {str(e)}")
            return None

    def fetch_ai_news(self) -> List[Dict]:
        """Fetch AI-related news."""
        try:
            query = ' OR '.join(f'"{topic}"' for topic in self.ai_topics)
            
            response = requests.get(
                'https://newsapi.org/v2/everything',
                params={
                    'q': query,
                    'sortBy': 'publishedAt',
                    'language': 'en',
                    'apiKey': self.news_api_key,
                    'pageSize': 10
                }
            )
            response.raise_for_status()
            articles = response.json().get('articles', [])
            
            relevant_articles = [
                article for article in articles
                if any(topic.lower() in (article.get('title', '') + article.get('description', '')).lower()
                      for topic in self.ai_topics)
            ]
            
            return relevant_articles[:5]
        except Exception as e:
            logging.error(f"News fetch error: {str(e)}")
            return []

    def generate_post(self, article: Dict) -> str:
        """Generate conversational post content."""
        try:
            prompt = f"""
            Create a natural, conversational post about this AI news:
            Title: {article.get('title', 'AI News')}
            Description: {article.get('description', 'Exciting developments in AI')}

            Requirements:
            - Write like a real person sharing interesting news
            - Include your perspective or a thought-provoking question
            - No promotional language or marketing speak
            - Keep it under 250 characters
            - Optional: one relevant emoji if it fits naturally
            - Sound genuine and interested in discussion
            """

            response = self.model.generate_content(prompt)
            post = response.text[:250]
            
            source = article.get('source', {}).get('name', '')
            if source:
                post = f"{post} (via {source})"
            
            return post[:280]
        except Exception as e:
            logging.error(f"Post generation error: {str(e)}")
            return f"Interesting AI development... what are your thoughts? (via {article.get('source', {}).get('name', 'Unknown Source')})"

    def get_notifications(self) -> List[Dict]:
        """Fetch recent notifications."""
        try:
            response = requests.get(
                f"{self.base_url}/app.bsky.notification.listNotifications",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={"limit": 20}
            )
            response.raise_for_status()
            return response.json().get("notifications", [])
        except Exception as e:
            logging.error(f"Error fetching notifications: {str(e)}")
            return []

    def get_post_thread(self, uri: str, depth: int = 1) -> Optional[Dict]:
        """Fetch a post's thread context."""
        try:
            response = requests.get(
                f"{self.base_url}/app.bsky.feed.getPostThread",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={"uri": uri, "depth": depth}
            )
            response.raise_for_status()
            return response.json().get("thread", {})
        except Exception as e:
            logging.error(f"Error fetching thread: {str(e)}")
            return None

    def should_reply_to_notification(self, notification: Dict) -> bool:
        """Determine if we should reply to a notification."""
        # Don't reply to our own posts
        if notification.get("author", {}).get("did") == self.did:
            return False
        
        # Only reply to replies and mentions
        if notification.get("reason") not in ["reply", "mention"]:
            return False
        
        # Check if the notification is new
        notification_time = datetime.fromisoformat(notification.get("indexedAt").replace('Z', '+00:00'))
        if notification_time <= self.last_checked_notification:
            return False
        
        return True

    def fetch_specific_news(self, query: str) -> List[Dict]:
        """Fetch news for a specific query."""
        try:
            response = requests.get(
                'https://newsapi.org/v2/everything',
                params={
                    'q': query,
                    'sortBy': 'publishedAt',
                    'language': 'en',
                    'apiKey': self.news_api_key,
                    'pageSize': 3
                }
            )
            response.raise_for_status()
            articles = response.json().get('articles', [])
            return articles[:3]
        except Exception as e:
            logging.error(f"Specific news fetch error: {str(e)}")
            return []

    def extract_news_request(self, text: str) -> Optional[str]:
        """Extract news request from user message."""
        news_keywords = [
            'latest news', 'recent news', 'news about', 
            'what\'s new', 'what is new', 'updates on',
            'tell me about', 'news on', 'heard about'
        ]
        
        text_lower = text.lower()
        
        if any(keyword in text_lower for keyword in news_keywords):
            try:
                prompt = f"""
                Extract the main topic or subject of this news request: {text}
                Only return the key topic(s) without any additional words or punctuation.
                For example:
                Input: "What's the latest news about ChatGPT and OpenAI?"
                Output: ChatGPT OpenAI
                Input: "Tell me recent news about AI regulation in Europe"
                Output: AI regulation Europe
                """
                
                response = self.model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                logging.error(f"News request extraction error: {str(e)}")
                return None
        return None

    def format_news_response(self, articles: List[Dict]) -> str:
        """Format news articles into a readable response."""
        if not articles:
            return "I couldn't find any recent news about that topic. Try asking about something else?"
        
        main_article = articles[0]
        response = f"📰 {main_article['title']}\n\n"
        
        if main_article.get('description'):
            response += f"{main_article['description'][:100]}...\n\n"
        
        source = main_article.get('source', {}).get('name', 'Unknown Source')
        response += f"(via {source})"
        
        if len(articles) > 1:
            response += "\n\nI found other recent articles about this too. Would you like to see more?"
        
        return response[:280]

    def handle_notifications(self) -> None:
        """Process and respond to notifications."""
        try:
            notifications = self.get_notifications()
            for notification in notifications:
                if self.should_reply_to_notification(notification):
                    reply_text = self.generate_reply(notification)
                    if reply_text:
                        self.create_post(reply_text, reply_to=notification)
                        time.sleep(2)  # Rate limiting
            
            self.last_checked_notification = datetime.now(UTC)
        except Exception as e:
            logging.error(f"Notification handling error: {str(e)}")

    def generate_reply(self, notification: Dict) -> str:
        """Generate a contextual reply."""
        try:
            thread = self.get_post_thread(notification.get("uri"))
            if not thread:
                return ""

            user_message = thread.get("post", {}).get("record", {}).get("text", "")
            user_handle = notification.get("author", {}).get("handle", "")
            
            news_query = self.extract_news_request(user_message)
            if news_query:
                articles = self.fetch_specific_news(news_query)
                return self.format_news_response(articles)
            
            prompt = f"""
            Generate a friendly and engaging reply to this user's message about AI:
            User (@{user_handle}): {user_message}

            Requirements:
            - Be conversational and natural
            - Add value to the discussion
            - Ask a relevant follow-up question if appropriate
            - Keep it under 250 characters
            - Be friendly but professional
            """

            response = self.model.generate_content(prompt)
            return response.text[:250]
        except Exception as e:
            logging.error(f"Reply generation error: {str(e)}")
            return "Thanks for your thoughts on AI! What's your take on recent developments in this space? 🤔"

    def post_news_update(self) -> None:
        """Post a single AI news update."""
        try:
            articles = self.fetch_ai_news()
            if articles:
                post_text = self.generate_post(articles[0])
                self.create_post(post_text)
                time.sleep(2)  # Rate limiting
        except Exception as e:
            logging.error(f"News update error: {str(e)}")

    def periodic_posting(self):
        """Post periodic AI-related updates."""
        try:
            prompt = random.choice(self.post_prompts)
            ai_post = self.generate_post({"title": prompt, "description": prompt})
            self.create_post(ai_post)
        except Exception as e:
            logging.error(f"Error in periodic posting: {str(e)}")

    def start(self):
        """Start the bot."""
        try:
            self.authenticate()
            
            def run_post_worker():
                while self.running:
                    try:
                        self.post_news_update()
                        time.sleep(1800)  # 30 minutes between posts
                    except Exception as e:
                        logging.error(f"Post worker error: {str(e)}")
                        time.sleep(60)

            def run_periodic_posting():
                while self.running:
                    try:
                        self.periodic_posting()
                        time.sleep(1800)  # 30 minutes between posts
                    except Exception as e:
                        logging.error(f"Periodic posting error: {str(e)}")
                        time.sleep(60)

            def run_notification_worker():
                while self.running:
                    try:
                        self.handle_notifications()
                        time.sleep(60)  # Check notifications every 1 minute
                    except Exception as e:
                        logging.error(f"Notification worker error: {str(e)}")
                        time.sleep(60)

            # Initialize worker threads
            post_thread = threading.Thread(target=run_post_worker, daemon=True)
            periodic_thread = threading.Thread(target=run_periodic_posting, daemon=True)
            notification_thread = threading.Thread(target=run_notification_worker, daemon=True)
            
            # Start workers
            post_thread.start()
            periodic_thread.start()
            notification_thread.start()
            
            def signal_handler(signum, frame):
                logging.info("Shutting down...")
                self.running = False
                
                # Wait for threads to finish
                post_thread.join(timeout=5)
                periodic_thread.join(timeout=5)
                notification_thread.join(timeout=5)
                
                logging.info("Cleanup complete")
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            while True:
                time.sleep(30)
                # Monitor threads
                if not post_thread.is_alive():
                    logging.error("Post worker died, restarting...")
                    post_thread = threading.Thread(target=run_post_worker, daemon=True)
                    post_thread.start()
                if not periodic_thread.is_alive():
                    logging.error("Periodic posting worker died, restarting...")
                    periodic_thread = threading.Thread(target=run_periodic_posting, daemon=True)
                    periodic_thread.start()
                if not notification_thread.is_alive():
                    logging.error("Notification worker died, restarting...")
                    notification_thread = threading.Thread(target=run_notification_worker, daemon=True)
                    notification_thread.start()

        except Exception as e:
            logging.error(f"Bot error: {str(e)}")
            self.running = False
            sys.exit(1)
        finally:
            # Cleanup
            logging.info("Shutting down bot...")
            self.running = False
            
            if 'post_thread' in locals() and post_thread.is_alive():
                post_thread.join(timeout=5)
            if 'periodic_thread' in locals() and periodic_thread.is_alive():
                periodic_thread.join(timeout=5)
            if 'notification_thread' in locals() and notification_thread.is_alive():
                notification_thread.join(timeout=5)
            
            logging.info("Bot shutdown complete")


def main():
    """Main entry point for the bot."""
    bot = None
    try:
        print("\n=== Starting BlueskyAI News Bot ===")
        print("AI-powered news aggregation and interaction bot")
        print("Version: 1.1.0\n")
        
        # Get credentials from environment variables or use defaults
        handle = os.getenv('BSKY_HANDLE',)
        app_password = os.getenv('BSKY_PASSWORD',)
        
        # Initialize and start the bot
        bot = BskyAINewsBot(handle, app_password)
        
        print(f"Starting bot with handle: {handle}")
        print("Press Ctrl+C to stop the bot\n")
        
        bot.start()
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        logging.error(f"Main function error: {str(e)}")
        sys.exit(1)
    finally:
        if bot:
            bot.running = False
            logging.info("Cleanup complete. Bot shutting down.")

if __name__ == "__main__":
    main()