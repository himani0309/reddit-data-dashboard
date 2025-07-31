import praw
import pandas as pd
import time

reddit = praw.Reddit(
    client_id="sid0vX-DZLf0iVGymNBLg",
    client_secret="OuycVLdUUMZGaKV-woHfyRrYmYsJg",
    user_agent="script:DigitalRupeeScraper:v1.0 (by u/Weary_Weight_5767)"
)

queries = [
    "Digital Rupee", "CBDC", "RBI Digital Currency",
    "e rupee", "Retail CBDC India", "Wholesale CBDC India"
]

results = []

for query in queries:
    print(f"\n🔍 Searching for: {query}")
    try:
        for submission in reddit.subreddit("all").search(query, sort="relevance", limit=15):
            results.append({
                "query": query,
                "title": submission.title,
                "subreddit": submission.subreddit.display_name,
                "url": submission.url,
                "created_utc": submission.created_utc
            })
        time.sleep(2)  # to avoid hitting rate limits
    except Exception as e:
        print(f"⚠️ Error for '{query}': {e}")

# Save to CSV
df = pd.DataFrame(results)
df["created_utc"] = pd.to_datetime(df["created_utc"], unit='s')
df.to_csv("reddit_scraped_digital_rupee.csv", index=False)

print(f"\n✅ Saved {len(df)} posts to reddit_scraped_digital_rupee.csv")
