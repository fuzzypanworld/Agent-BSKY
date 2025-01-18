# Bsky AI News Bot

## Overview
The Bsky AI News Bot is a Python-based bot that integrates with Bluesky Social to post and interact with AI-related content. It uses AI-driven prompts to generate creative posts and replies, fetches relevant AI news from APIs, and handles notifications for engagement.

## Features
- **Bluesky Integration**: Authenticate, post, and manage replies on Bluesky Social.
- **AI-Powered Content Generation**: Leverages Generative AI (Gemini API) to create engaging and conversational posts.
- **News Aggregation**: Fetches AI-related news from NewsAPI based on trending topics and user queries.
- **Notification Management**: Responds to mentions and replies with context-aware AI-generated responses.
- **Topic Tracking**: Tracks specific AI topics like GPT-4, ChatGPT, Claude, and more.

## Prerequisites
- Python 3.8 or above.
- API keys for:
  - Bluesky Social
  - NewsAPI
  - Gemini API (for generative AI).

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/fuzzypanworld/Agent-BSKY.git
   ```
2. Install dependencies
3. Set up environment variables:
   ```bash
   export BLUESKY_HANDLE="your-handle"
   export BLUESKY_PASSWORD="your-password"
   export NEWS_API_KEY="your-news-api-key"
   export GEMINI_API_KEY="your-gemini-api-key"
   ```

## Usage
### Run the Bot
Start the bot using:
```bash
python main.py
```

### Features in Detail
1. **Posting AI News**:
   - Fetches top AI news from NewsAPI and generates a conversational post using Generative AI.
   - Posts include a summary of the article and a thought-provoking question.

2. **Handling Notifications**:
   - Fetches mentions and replies from Bluesky Social.
   - Responds with AI-generated content based on the context of the notification.

3. **Custom News Requests**:
   - Extracts user queries for specific AI news topics and fetches relevant articles.

4. **Thread Engagement**:
   - Engages with threads by responding to specific posts in the context of ongoing discussions.

### Example Outputs
**AI News Post**:
> "Breakthrough in GPT-4 technology: OpenAI reveals new capabilities for developers. Could this change the way we build AI apps? (via TechCrunch)"

**Notification Reply**:
> "Great point! AI ethics is a crucial area to focus on as we advance in this field. What are your thoughts on implementing these principles?"

## Logging
Logs are stored in `bsky_bot.log` and printed to the console for easy debugging.

## Configuration
### Prompts
Prompts for generating posts and replies are customizable. Edit the `self.post_prompts` list in the `BskyAINewsBot` class to update them.

### AI Topics
The bot tracks specific AI topics such as "GPT-4", "ChatGPT", "Anthropic", etc. Update the `self.ai_topics` list as needed.

## Troubleshooting
- **Authentication Issues**:
  - Ensure your Bluesky handle and app password are correct.
  - Verify the Bluesky Social API is operational.

- **News Fetching Errors**:
  - Confirm your NewsAPI key is valid and has quota available.

- **AI Content Generation Errors**:
  - Verify your Gemini API key is active and configured correctly.

## Future Enhancements
- Add support for scheduling posts.
- Implement sentiment analysis for replies.
- Expand topic tracking to include user-defined topics.

## License
This project is licensed under the MIT License. See `LICENSE` for details.

## Acknowledgments
- [Bluesky Social](https://bsky.app/)
- [NewsAPI](https://newsapi.org/)
- [Generative AI (Gemini)](https://example.com/gemini-api-docs)

