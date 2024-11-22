from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time

def setup_driver():
    """Set up the Selenium WebDriver with headless options."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    
    service = Service('/path/to/chromedriver')  # Update this path to your chromedriver
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def scrape_tweets(search_query, num_tweets=5):
    """Scrape tweets from x.com based on a search query."""
    base_url = f"https://x.com/search?q={search_query}&src=typed_query"
    driver = setup_driver()
    driver.get(base_url)

    # Wait for the page to load (adjust as needed)
    time.sleep(5)

    # Scroll to load more tweets, if necessary
    scroll_pause_time = 2  # Adjust scroll pause duration
    last_height = driver.execute_script("return document.body.scrollHeight")

    while len(driver.find_elements(By.CSS_SELECTOR, "article")) < num_tweets:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_pause_time)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:  # Break if no more tweets are loaded
            break
        last_height = new_height

    # Parse tweets
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')
    tweets = soup.find_all("article", limit=num_tweets)

    tweet_texts = []
    for tweet in tweets:
        try:
            content = tweet.find("div", {"data-testid": "tweetText"}).text
            tweet_texts.append(content)
        except AttributeError:
            continue  # Skip if tweet text is not found

    driver.quit()
    return tweet_texts

def main():
    print("Welcome to the X.com Tweet Scraper!")
    search_query = input("Enter your search query (e.g., AI, Bitcoin, etc.): ").strip()
    num_tweets = int(input("Enter the number of tweets to scrape: "))

    print("\nScraping tweets...")
    try:
        tweets = scrape_tweets(search_query, num_tweets)
        print("\nTweets Retrieved:")
        for i, tweet in enumerate(tweets, 1):
            print(f"{i}. {tweet}\n")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
