from atproto import Client
from datetime import datetime, timedelta
from collections import defaultdict
import os
import colorama
from colorama import Fore, Style
import time

# Initialize colorama for Windows support
colorama.init()

class SimpleBlueskyStats:
    def __init__(self, handle: str, password: str):
        self.client = Client()
        self.handle = handle
        self.password = password
        self.login()

    def login(self):
        """Login to Bluesky"""
        try:
            self.client.login(self.handle, self.password)
            print(f"{Fore.GREEN}✓ Successfully logged in as {self.handle}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}✗ Login failed: {str(e)}{Style.RESET_ALL}")
            exit(1)

    def get_profile_stats(self):
        """Get basic profile statistics"""
        try:
            profile = self.client.get_profile(self.handle)
            return {
                'followers': profile.followers_count,
                'following': profile.follows_count,
                'posts': profile.posts_count,
                'display_name': profile.display_name
            }
        except Exception as e:
            print(f"{Fore.RED}✗ Failed to get profile stats: {str(e)}{Style.RESET_ALL}")
            return None

    def get_recent_posts(self, hours=24):
        """Get posts from the last specified hours"""
        posts = []
        cursor = None
        start_time = datetime.now() - timedelta(hours=hours)

        try:
            while True:
                feed = self.client.get_author_feed(self.handle, cursor=cursor)
                
                for post in feed.feed:
                    post_time = datetime.strptime(post.post.indexed_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                    if post_time < start_time:
                        return posts
                    posts.append(post.post)

                cursor = feed.cursor
                if not cursor or not feed.feed:
                    break

                # Add a small delay to avoid rate limiting
                time.sleep(0.5)

        except Exception as e:
            print(f"{Fore.RED}✗ Failed to get recent posts: {str(e)}{Style.RESET_ALL}")
            return posts

        return posts

    def analyze_posts(self, posts):
        """Analyze posts for basic metrics"""
        stats = {
            'total_posts': len(posts),
            'total_likes': 0,
            'total_reposts': 0,
            'hashtags': defaultdict(int),
            'post_times': defaultdict(int),
            'avg_length': 0,
            'total_length': 0
        }

        for post in posts:
            # Count likes and reposts
            stats['total_likes'] += post.like_count
            stats['total_reposts'] += post.repost_count

            # Analyze text
            if hasattr(post.record, 'text'):
                text = post.record.text
                stats['total_length'] += len(text)
                
                # Count hashtags
                words = text.split()
                for word in words:
                    if word.startswith('#'):
                        stats['hashtags'][word.lower()] += 1

            # Track posting time
            post_time = datetime.strptime(post.indexed_at, "%Y-%m-%dT%H:%M:%S.%fZ")
            stats['post_times'][post_time.hour] += 1

        if stats['total_posts'] > 0:
            stats['avg_length'] = stats['total_length'] / stats['total_posts']

        return stats

    def display_stats(self):
        """Display all statistics in a formatted way"""
        print(f"\n{Fore.CYAN}=== Bluesky Account Statistics ==={Style.RESET_ALL}")
        
        # Profile Stats
        profile_stats = self.get_profile_stats()
        if profile_stats:
            print(f"\n{Fore.YELLOW}Profile Statistics:{Style.RESET_ALL}")
            print(f"Display Name: {profile_stats['display_name']}")
            print(f"Followers: {profile_stats['followers']:,}")
            print(f"Following: {profile_stats['following']:,}")
            print(f"Total Posts: {profile_stats['posts']:,}")

        # Recent Post Analysis
        print(f"\n{Fore.YELLOW}Last 24 Hours Activity:{Style.RESET_ALL}")
        recent_posts = self.get_recent_posts(hours=24)
        stats = self.analyze_posts(recent_posts)

        print(f"Posts made: {stats['total_posts']}")
        print(f"Total likes received: {stats['total_likes']:,}")
        print(f"Total reposts received: {stats['total_reposts']:,}")
        
        if stats['total_posts'] > 0:
            print(f"Average post length: {stats['avg_length']:.1f} characters")

        # Display top hashtags
        if stats['hashtags']:
            print(f"\n{Fore.YELLOW}Top Hashtags Used:{Style.RESET_ALL}")
            sorted_hashtags = sorted(stats['hashtags'].items(), key=lambda x: x[1], reverse=True)[:5]
            for tag, count in sorted_hashtags:
                print(f"{tag}: {count} times")

        # Display posting time distribution
        if stats['post_times']:
            print(f"\n{Fore.YELLOW}Posting Time Distribution:{Style.RESET_ALL}")
            for hour in range(24):
                if stats['post_times'][hour] > 0:
                    print(f"{hour:02d}:00 - {hour:02d}:59: {stats['post_times'][hour]} posts")

def main():
    print(f"{Fore.CYAN}Bluesky Stats Collector{Style.RESET_ALL}")
    
    # Get credentials from environment variables
    handle = 'learninwithak.bsky.social'
    password = 'Atharva5454'

    if not handle or not password:
        print(f"{Fore.RED}Error: Please set BSKY_HANDLE and BSKY_PASSWORD environment variables{Style.RESET_ALL}")
        print("\nExample:")
        print("set BSKY_HANDLE=yourusername.bsky.social")
        print("set BSKY_PASSWORD=your-app-password")
        return

    try:
        stats = SimpleBlueskyStats(handle, password)
        stats.display_stats()
    except Exception as e:
        print(f"{Fore.RED}An error occurred: {str(e)}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()