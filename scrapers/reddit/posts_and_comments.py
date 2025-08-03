"""
Scrapy spider to fetch posts and comments info related to specific keywords from reddit.

Run using: python ./scrapers/reddit/posts_and_comments_spider.py --username abcd --password 123456 --storage_state './tmp/sessions/' --outdir ./output/reddit/ --keywords ""
"""

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import scrapy
from bs4 import BeautifulSoup
from functions import (
    ensure_session,
    get_cursor_token,
    get_posts,
    is_post_relevant,
    parse_comments_structure,
    parse_post_details,
    retry_login_and_reload,
)
from scrapy import signals
from scrapy.crawler import CrawlerProcess
from scrapy.exceptions import DontCloseSpider


class StandardSpider(scrapy.Spider):
    name = "posts_and_comments"

    # run one request at a time, write to CSV
    custom_settings = {
        "LOG_LEVEL": "ERROR",
        "ROBOTSTXT_OBEY": False,
        "CLOSESPIDER_ERRORCOUNT": 1,
        # — concurrency —
        "CONCURRENT_REQUESTS": 20,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 20,
        # # — fixed delay (with random jitter) —
        # "DOWNLOAD_DELAY": 1.0,  # at least 1 s between requests to the same host
        # "RANDOMIZE_DOWNLOAD_DELAY": True,  # scramble that 1 s to something between 0.5–1.5 s
        # # — automatic throttling —
        # "AUTOTHROTTLE_ENABLED": True,
        # "AUTOTHROTTLE_START_DELAY": 1.0,  # initial delay
        # "AUTOTHROTTLE_MAX_DELAY": 10.0,  # back off up to 10 s if the server is slow
        # "AUTOTHROTTLE_TARGET_CONCURRENCY": 5.0,  # aim for ~5 concurrent requests per server
        # — cookie debugging —
        # "COOKIES_DEBUG": True,
    }

    SCROLL_LIMIT = 40
    SEARCH_FILTERS = [
        "&type=posts&sort=relevance&t=year",
        "&type=posts&sort=hot",
        # "&type=posts&sort=top",
        # "&type=posts&sort=new",
    ]
    BASE_URL = "https://www.reddit.com/"
    SEARCH_URL = f"https://www.reddit.com/search/?q="
    PROFILE_URL = f"https://www.reddit.com/user/"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.username = kwargs.get("username")
        self.password = kwargs.get("password")
        # build the all_skus.csv and accounts.csv files path
        self.outdir = Path(kwargs.get("outdir"))
        self.outdir.mkdir(parents=True, exist_ok=True)
        self.output_csv_path = self.outdir / "output.csv"

        storage_state = kwargs.get("storage_state")
        os.makedirs(Path(storage_state), exist_ok=True)
        self.session_file = Path(storage_state) / f"{self.username}.json"
        self._login_retried = False

        # Load existing posts if CSV file exists
        self.all_posts = []
        if self.output_csv_path.exists():
            try:
                print(f"Loading existing posts from {self.output_csv_path}")
                df = pd.read_csv(self.output_csv_path)
                # Convert DataFrame to list of dictionaries
                self.all_posts = df.to_dict("records")
                print(f"Loaded {len(self.all_posts)} existing posts")
            except Exception as e:
                print(f"Error loading existing posts: {e}")
                self.all_posts = []
        else:
            print(
                f"No existing posts file found at {self.output_csv_path}, starting fresh"
            )

        keywords_str = kwargs.get("keywords")
        self.keywords = (
            [kw.strip() for kw in keywords_str.split(",")] if keywords_str else []
        )

        # Track search completion
        self.total_searches = 0
        self.completed_searches = 0

        # Track progress for printing
        self.last_printed_count = len(self.all_posts)  # Start from current count

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        # fmt:off
        # Dynamically set up the feed export to write to our all_skus_csv_path
        crawler.settings.set(
            "FEEDS",{str(spider.output_csv_path): {"format": "csv","overwrite": False}},priority="spider")
        # "FEEDS",{str(spider.output_csv_path): {"format": "csv","overwrite": True}},priority="spider")
        # fmt:on
        return spider

    def start_requests(self):
        ensure_session(self)
        yield scrapy.Request(
            self.PROFILE_URL + self.username + "/",
            headers=self.headers,
            cookies=self.cookies,
            callback=self.login_success_check,
            errback=self.handle_login_error,
            dont_filter=True,
        )

    def handle_login_error(self, failure):
        print(f"Request failed: {failure.value}")
        retry_login_and_reload(self)
        yield scrapy.Request(
            self.PROFILE_URL + self.username + "/",
            headers=self.headers,
            cookies=self.cookies,
            callback=self.login_success_check,
            dont_filter=True,
        )

    # ────────────────────────────────────────────────────────────────
    # Account discovery & scheduling
    # ────────────────────────────────────────────────────────────────
    def login_success_check(self, response):
        if "Customize your profile" in response.text:
            print("✅ Login successful")

            search_urls = []
            # build the search urls
            for keyword in self.keywords:
                for filter in self.SEARCH_FILTERS:
                    url = self.SEARCH_URL + keyword + filter
                    search_urls.append(url)

            # Calculate total number of searches to track completion
            self.total_searches = len(search_urls)
            print(f"Total searches to complete: {self.total_searches}")

            for url in search_urls:
                yield scrapy.Request(
                    url,
                    headers=self.headers,
                    cookies=self.cookies,
                    callback=self.parse_search_page,
                    meta={
                        "url": url,
                        "scroll_count": 0,
                    },
                    dont_filter=True,
                )

        else:
            print(f"❌ Login failed with status {response.status}. Re-logging in.")
            retry_login_and_reload(self)
            yield scrapy.Request(
                self.PROFILE_URL + self.username + "/",
                headers=self.headers,
                cookies=self.cookies,
                callback=self.login_success_check,
                dont_filter=True,
            )

    def parse_search_page(self, response):
        url = response.meta.get("url")
        scroll_count = response.meta.get("scroll_count")

        posts = get_posts(response.text)
        # Filter out posts with duplicate titles
        existing_urls = set(post["post_url"] for post in self.all_posts)
        unique_posts = [
            post for post in posts if post.get("post_url") not in existing_urls
        ]
        self.all_posts.extend(unique_posts)
        cursor_token = get_cursor_token(response.text)

        # Print progress if at least 50 posts have been added since last print
        current_count = len(self.all_posts)
        if current_count - self.last_printed_count >= 50:
            print(f"Collected {current_count} posts so far")
            self.last_printed_count = current_count

        # now fetch the comments for each post
        for post in unique_posts:
            yield scrapy.Request(
                post["post_url"],
                headers=self.headers,
                cookies=self.cookies,
                callback=self.parse_post_page,
                meta={
                    "post_url": post["post_url"],
                },
                dont_filter=True,
            )

        if scroll_count < self.SCROLL_LIMIT:
            yield scrapy.Request(
                url + f"&cursor={cursor_token}",
                headers=self.headers,
                cookies=self.cookies,
                callback=self.parse_search_page,
                meta={
                    "url": url,
                    "cursor_token": cursor_token,
                    "scroll_count": scroll_count + 1,
                },
                dont_filter=True,
            )
        else:
            print(f"Total posts found for {url}: {len(self.all_posts)}")
            # Mark this search as completed
            self.completed_searches += 1
            print(
                f"Completed posts search {self.completed_searches}/{self.total_searches}"
            )

        # # Check if all searches are complete
        # if self.completed_searches >= self.total_searches:
        #     print("All searches completed! Proceeding to next step...")
        #     print(f"Total posts collected across all searches: {len(self.all_posts)}")

    def parse_post_page(self, response):
        post_url = response.meta.get("post_url")

        # Extract post data
        upvote, comment_count, post_body = parse_post_details(response.text)

        # Find the post in self.all_posts with matching href and update its fields
        for post_data in self.all_posts:
            if post_data.get("post_url") == post_url:
                # post_data["upvote"] = upvote
                # post_data["comment_count"] = comment_count
                post_data["post_body"] = post_body
                # post_data["scraped_at"] = datetime.now().isoformat()

        # now fetch the comments for this post
        parsed = urlparse(response.url)
        parts = parsed.path.strip("/").split("/")
        subreddit = parts[1]  # 'subreddit'
        post_id = parts[3]  # 'post_id'
        comments_url = f"https://www.reddit.com/svc/shreddit/comments/r/{subreddit}/t3_{post_id}?render-mode=partial&seeker-session=true&sort=confidence&inline-refresh=true"

        yield scrapy.Request(
            comments_url,
            headers=self.headers,
            cookies=self.cookies,
            callback=self.parse_comments_page,
            meta={
                "post_url": post_url,
            },
            dont_filter=True,
        )

    def parse_comments_page(self, response):
        post_url = response.meta.get("post_url")

        # Parse comments from the HTML response
        comments_data = parse_comments_structure(response.text)

        # Find the post in self.all_posts and add comments data
        for post_data in self.all_posts:
            if post_data.get("post_url") == post_url:
                # fmt:off
                post_data["comment_1"] = comments_data['comments'][0] if comments_data.get('comments') and len(comments_data['comments']) > 0 else None
                post_data["comment_2"] = comments_data['comments'][1] if comments_data.get('comments') and len(comments_data['comments']) > 1 else None
                post_data["comment_3"] = comments_data['comments'][2] if comments_data.get('comments') and len(comments_data['comments']) > 2 else None
                post_data["comment_4"] = comments_data['comments'][3] if comments_data.get('comments') and len(comments_data['comments']) > 3 else None
                post_data["comment_5"] = comments_data['comments'][4] if comments_data.get('comments') and len(comments_data['comments']) > 4 else None
                post_data["scraped_at"] = datetime.now().isoformat()
                # fmt:on
                yield post_data


# Entry point
if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--storage_state", required=True)
    p.add_argument("--outdir", default="./tmp/output", help="Output directory")
    p.add_argument(
        "--keywords",
        required=True,
        help="Keywords separated by comma to search in reddit",
    )
    args = p.parse_args()

    proc = CrawlerProcess()
    crawler = proc.create_crawler(StandardSpider)

    proc.crawl(
        crawler,
        username=args.username,
        password=args.password,
        storage_state=args.storage_state,
        outdir=args.outdir,
        keywords=args.keywords,
    )
    proc.start()
