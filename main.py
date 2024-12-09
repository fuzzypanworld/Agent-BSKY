import os
import time
import threading
import requests
import json
import logging
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
        self.processed_comments = set()
        self.recent_threads = []
        self.running = True
        self.last_article = None
        
        # Configure APIs
        self.news_api_key = os.getenv('NEWS_API_KEY', '8ed5c4cbc1b14e08a5304ff4ab235179')
        genai.configure(api_key=os.getenv('GEMINI_API_KEY', 'AIzaSyCXijVmfBPq2e4p8Ouj6KyjKw0lWOjwb7w'))
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

            if reply_to:
                post_data["reply"] = {
                    "root": {
                        "uri": reply_to["root_uri"],
                        "cid": reply_to["root_cid"]
                    },
                    "parent": {
                        "uri": reply_to["parent_uri"],
                        "cid": reply_to["parent_cid"]
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
            # Create query focusing on major AI topics
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
            
            # Filter for relevant articles
            relevant_articles = [
                article for article in articles
                if any(topic.lower() in (article.get('title', '') + article.get('description', '')).lower()
                      for topic in self.ai_topics)
            ]
            
            return relevant_articles[:5]
        except Exception as e:
            logging.error(f"News fetch error: {str(e)}")
            return []

    def generate_post(self, article: Dict, tone: Optional[str] = None) -> str:
        """Generate conversational post content."""
        try:
            self.last_article = article  # Store for tone change requests
            
            prompt = f"""
            Create a natural, conversational post about this AI news:
            Title: {article['title']}
            Description: {article['description']}

            Requirements:
            - Write like a real person sharing interesting news
            - Include your perspective or a thought-provoking question
            - No promotional language or marketing speak
            - Keep it under 250 characters
            - Optional: one relevant emoji if it fits naturally
            - Sound genuine and interested in discussion
            """

            if tone:
                prompt += f"\nMatch this specific tone/style: {tone}"

            response = self.model.generate_content(prompt)
            post = response.text[:250]
            
            source = article.get('source', {}).get('name', '')
            if source:
                post = f"{post} (via {source})"
            
            return post[:280]
        except Exception as e:
            logging.error(f"Post generation error: {str(e)}")
            return f"Interesting AI development... what are your thoughts on this? (via {article.get('source', {}).get('name', '')})"

    def get_post_info(self, uri: str) -> Optional[Dict]:
        """Get post information including CID."""
        try:
            parts = uri.split('/')
            repo = parts[-3]
            rkey = parts[-1]
            
            response = requests.get(
                f"{self.base_url}/com.atproto.repo.getRecord",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={
                    "repo": repo,
                    "collection": "app.bsky.feed.post",
                    "rkey": rkey
                }
            )
            response.raise_for_status()
            data = response.json()
            return {
                "uri": uri,
                "cid": data["cid"]
            }
        except Exception as e:
            logging.error(f"Error getting post info: {str(e)}")
            return None

    def create_thread(self) -> Optional[str]:
        """Create a news thread."""
        try:
            articles = self.fetch_ai_news()
            if not articles:
                return None

            # Create root post
            root_text = self.generate_post(articles[0])
            root_uri = self.create_post(root_text)
            if not root_uri:
                return None

            root_info = self.get_post_info(root_uri)
            if not root_info:
                return None

            # Add to recent threads
            self.recent_threads.append({
                'uri': root_uri,
                'cid': root_info['cid'],
                'timestamp': datetime.now(UTC)
            })

            # Create replies
            current_uri = root_uri
            current_cid = root_info['cid']
            
            for article in articles[1:]:
                reply_text = self.generate_post(article)
                success = self.create_post(
                    reply_text,
                    reply_to={
                        "root_uri": root_uri,
                        "root_cid": root_info['cid'],
                        "parent_uri": current_uri,
                        "parent_cid": current_cid
                    }
                )
                if success:
                    current_info = self.get_post_info(success)
                    if current_info:
                        current_uri = success
                        current_cid = current_info['cid']
                time.sleep(2)

            return root_uri
        except Exception as e:
            logging.error(f"Thread creation error: {str(e)}")
            return None

    def generate_reply(self, comment_text: str, is_mentioned: bool = False) -> str:
        """Generate a natural reply."""
        try:
            if "Change this post into" in comment_text:
                # Handle tone change request
                tone = comment_text.split("Change this post into")[1].split("tone")[0].strip()
                return self.generate_post(self.last_article, tone=tone)

            prompt = f"""
            Generate a natural, conversational reply to: '{comment_text}'

            Requirements:
            - Respond like a real person having a conversation
            - If they asked a question, give your perspective
            - If they made a point, engage with their idea
            - Keep it under 280 characters
            - Sound genuine and interested
            {"- They mentioned you directly, so acknowledge that" if is_mentioned else ""}
            """

            response = self.model.generate_content(prompt)
            return response.text[:280]
        except Exception as e:
            logging.error(f"Reply generation error: {str(e)}")
            return "Thanks for sharing your thoughts! What made you think about it that way?"

    def process_comments(self, thread_info: Dict) -> None:
        """Process and reply to comments."""
        try:
            if not self.access_token:
                self.authenticate()

            response = requests.get(
                f"{self.base_url}/app.bsky.feed.getPostThread",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={"uri": thread_info['uri'], "depth": 1}
            )
            response.raise_for_status()
            data = response.json()

            replies = data.get('thread', {}).get('replies', [])
            logging.info(f"Found {len(replies)} replies to process")

            for reply in replies:
                try:
                    reply_post = reply.get('post', {})
                    reply_uri = reply_post.get('uri')
                    comment_text = reply_post.get('record', {}).get('text', '')

                    if not reply_uri or not comment_text:
                        continue

                    if reply_uri in self.processed_comments:
                        continue

                    is_mentioned = f"@{self.handle}" in comment_text
                    should_reply = is_mentioned or reply_post.get('record', {}).get('reply', {}).get('parent', {}).get('uri') in [t['uri'] for t in self.recent_threads]

                    if not should_reply:
                        continue

                    reply_info = self.get_post_info(reply_uri)
                    if not reply_info:
                        continue

                    reply_text = self.generate_reply(comment_text, is_mentioned)
                    
                    success = self.create_post(
                        reply_text,
                        reply_to={
                            "root_uri": thread_info['uri'],
                            "root_cid": thread_info['cid'],
                            "parent_uri": reply_uri,
                            "parent_cid": reply_info['cid']
                        }
                    )

                    if success:
                        self.processed_comments.add(reply_uri)
                        logging.info(f"Replied to comment: {reply_uri}")
                    time.sleep(1)

                except Exception as e:
                    logging.error(f"Error processing reply: {str(e)}")
                    continue

        except Exception as e:
            logging.error(f"Comment processing error: {str(e)}")

    def start(self):
        """Start the bot."""
        try:
            self.authenticate()
            
            def run_post_worker():
                while self.running:
                    try:
                        thread_uri = self.create_thread()
                        if thread_uri:
                            logging.info(f"Created thread: {thread_uri}")
                        time.sleep(1800)  # 30 minutes between threads
                    except Exception as e:
                        logging.error(f"Post worker error: {str(e)}")
                        time.sleep(60)

            def run_comment_worker():
                while self.running:
                    try:
                        for thread in self.recent_threads[:]:
                            self.process_comments(thread)
                        time.sleep(10)  # Check every 10 seconds
                    except Exception as e:
                        logging.error(f"Comment worker error: {str(e)}")
                        time.sleep(30)

            # Start workers
            post_thread = threading.Thread(target=run_post_worker, daemon=True)
            comment_thread = threading.Thread(target=run_comment_worker, daemon=True)
            
            post_thread.start()
            comment_thread.start()
            
            def signal_handler(signum, frame):
                logging.info("Shutting down...")
                self.running = False
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
                if not comment_thread.is_alive():
                    logging.error("Comment worker died, restarting...")
                    comment_thread = threading.Thread(target=run_comment_worker, daemon=True)
                    comment_thread.start()

        except Exception as e:
            logging.error(f"Bot error: {str(e)}")
            sys.exit(1)

def main():
    bot = BskyAINewsBot('learninwithak.bsky.social', 'p7za-ej2v-uq2k-qjzo')
    bot.start()

if __name__ == "__main__":
    main()