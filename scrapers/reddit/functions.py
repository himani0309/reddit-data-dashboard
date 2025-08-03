import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# ────────────────────────────────────────────────────────────────
# Session management
# ────────────────────────────────────────────────────────────────
def ensure_session(self):
    if not self.session_file.exists():
        print(f"No session file at {self.session_file}; logging in…")
        login_via_cli(self)
    else:
        print(f"Using existing session file {self.session_file}")
    reload_session(self)


def reload_session(self):
    """Load 'reddit_session' cookie and headers from self.session_file."""
    try:
        raw = json.loads(self.session_file.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise RuntimeError(
            f"Could not find or open session file: {self.session_file}"
        ) from e

    cookies = {
        c["name"]: c["value"]
        for c in raw.get("cookies", [])
        if c.get("name") == "reddit_session"
    }
    if not cookies:
        self.logger.warning(f"'reddit_session' cookie not found in {self.session_file}")
    self.cookies = cookies
    self.headers = raw.get("headers", {})


def login_via_cli(self):
    script = Path(__file__).parent / "getcookies.py"
    cmd = [
        sys.executable,
        str(script),
        "--username",
        self.username,
        "--password",
        self.password,
        "--storage-file",
        str(self.session_file),
    ]
    res = subprocess.run(cmd, text=True)
    if res.returncode != 0:
        err = (res.stderr or "").strip()
        self.logger.error(f"Login helper failed: {err}")
        raise RuntimeError("Authentication failed via CLI")
    print(f"✅ Login helper succeeded:\n{(res.stdout or '').strip()}")


def retry_login_and_reload(self):
    """Delete bad session and attempt login once more."""
    if self._login_retried:
        raise RuntimeError("Login failed after multiple attempts")
    self._login_retried = True
    try:
        self.session_file.unlink()
    except OSError:
        pass
    print("❌ Invalid credentials, retrying login…")
    login_via_cli(self)
    reload_session(self)
    return True


# ────────────────────────────────────────────────────────────────
# Scraping helper functions
# ────────────────────────────────────────────────────────────────
def get_cursor_token(html):
    # Look for faceplate-partial src attribute containing 'cursor='
    match = re.search(r'src="[^"]*cursor=([^"&]*)', html)
    if match:
        return match.group(1)
    return None


def get_posts(response_html):
    soup = BeautifulSoup(response_html, "html.parser")

    posts_data = []
    # Each post is inside a <search-telemetry-tracker> with data-testid="search-sdui-post"
    for post in soup.find_all(
        "search-telemetry-tracker", attrs={"data-testid": "search-sdui-post"}
    ):
        post_data = {}

        # Title and post href
        title_tag = post.find("a", attrs={"data-testid": "post-title"})
        if not title_tag:
            # Sometimes the title is in a different anchor with data-testid="post-title-text"
            title_tag = post.find("a", attrs={"data-testid": "post-title-text"})
        if title_tag:
            post_data["post_title"] = title_tag.get("aria-label") or title_tag.get_text(
                strip=True
            )
            post_data["post_url"] = "https://www.reddit.com" + title_tag.get("href")
        else:
            post_data["post_title"] = None
            post_data["post_url"] = None

        # Subreddit name
        subreddit_span = post.find("span", class_="truncate")
        if subreddit_span:
            post_data["subreddit"] = subreddit_span.get_text(strip=True)
        else:
            post_data["subreddit"] = None

        # Time ago string
        # Try to get the timestamp from <faceplate-timeago>
        timeago = post.find("faceplate-timeago")
        if timeago:
            # Try to get the 'ts' attribute (ISO timestamp)
            ts = timeago.get("ts")
            if ts:
                post_data["post_date"] = ts
            else:
                # Sometimes the timeago tag has a 'title' attribute
                post_data["post_date"] = timeago.get("title")
        else:
            # Fallback: look for a <span> with a time string ending in "ago"
            time_span = post.find("span", string=re.compile(r"ago$"))
            post_data["post_date"] = (
                time_span.get_text(strip=True) if time_span else None
            )

        # Total votes
        # Look for <div data-testid="search-counter-row">, then <faceplate-number> for votes
        votes = None
        counter_row = post.find("div", attrs={"data-testid": "search-counter-row"})
        if counter_row:
            vote_span = counter_row.find_all("span")
            if vote_span:
                # The first <span> should contain the votes
                votes_faceplate = vote_span[0].find("faceplate-number")
                if votes_faceplate and votes_faceplate.has_attr("number"):
                    votes = votes_faceplate["number"]
                else:
                    # Fallback: try to extract digits from the text
                    text = vote_span[0].get_text()
                    m = re.search(r"(\d[\d,]*)", text)
                    if m:
                        votes = m.group(1).replace(",", "")
        post_data["post_upvotes"] = votes

        # Total comments
        comments = None
        if counter_row:
            comment_spans = counter_row.find_all("span")
            if len(comment_spans) > 2:
                # The third <span> should contain the comments
                comments_faceplate = comment_spans[2].find("faceplate-number")
                if comments_faceplate and comments_faceplate.has_attr("number"):
                    comments = comments_faceplate["number"]
                else:
                    # Fallback: try to extract digits from the text
                    text = comment_spans[2].get_text()
                    m = re.search(r"(\d[\d,]*)", text)
                    if m:
                        comments = m.group(1).replace(",", "")
        post_data["total_comments"] = comments

        # Only append if all fields are present (not None or empty)
        required_fields = [
            "post_title",
            "post_url",
            "subreddit",
            "post_date",
            "post_upvotes",
            "total_comments",
        ]
        if all(post_data.get(field) not in [None, ""] for field in required_fields):
            posts_data.append(post_data)

    return posts_data


def parse_post_details(response_html):
    soup = BeautifulSoup(response_html, "html.parser")

    score = None
    comment_count = None
    body = None

    # Find the shreddit-post element to extract score and comment count
    shreddit_post = soup.find("shreddit-post")
    if shreddit_post:
        # Extract score
        score_attr = shreddit_post.get("score")
        if score_attr:
            try:
                score = int(score_attr)
            except (ValueError, TypeError):
                score = 0

        # Extract comment count
        comment_count_attr = shreddit_post.get("comment-count")
        if comment_count_attr:
            try:
                comment_count = int(comment_count_attr)
            except (ValueError, TypeError):
                comment_count = 0

    # Extract post body
    text_body_div = soup.find(
        "div", class_="text-neutral-content", attrs={"slot": "text-body"}
    )
    if text_body_div:
        # Find the content div with the actual text
        content_div = text_body_div.find("div", class_="md text-14-scalable")
        if content_div:
            # Get all text content, removing extra whitespace
            body_text = content_div.get_text(strip=True)
            body = body_text
    else:
        body = "None"

    return score, comment_count, body


def parse_comments_structure(html_content):
    """
    Parse Reddit comments and create a hierarchical structure.

    Args:
        html_content (str): HTML content from Reddit comments page

    Returns:
        dict: Hierarchical structure with total comments count and comment list
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Find the main comment tree
    comment_tree = soup.find("shreddit-comment-tree")
    if not comment_tree:
        return {"total_comments": "0", "comments": []}

    # Get total comments count
    total_comments = comment_tree.get("totalComments", "0")

    # Find all comment elements
    comment_elements = comment_tree.find_all("shreddit-comment")

    # Create a flat list of all comments
    all_comments = []
    for comment_elem in comment_elements:
        comment_data = extract_comment_data(comment_elem)
        if comment_data:
            all_comments.append(comment_data)

    # Build proper hierarchical structure using parentId
    comments_by_id = {comment["comment_id"]: comment for comment in all_comments}
    root_comments = []

    # First, find all root comments (depth 0)
    for comment in all_comments:
        if comment["depth"] == 0:
            root_comments.append(comment)

    # Then, assign replies to their proper parents using parentId
    for comment in all_comments:
        if comment["depth"] > 0 and "parent_id" in comment:
            parent_id = comment["parent_id"]
            if parent_id in comments_by_id:
                parent_comment = comments_by_id[parent_id]
                if "replies" not in parent_comment:
                    parent_comment["replies"] = []
                parent_comment["replies"].append(comment)

    return {"total_comments": total_comments, "comments": root_comments}


def extract_comment_data(comment_elem):
    """
    Extract data from a single shreddit-comment element.

    Args:
        comment_elem: BeautifulSoup element for a single comment

    Returns:
        dict: Comment data including text, upvotes, author, and replies
    """
    try:
        # Extract basic comment attributes
        comment_id = comment_elem.get("thingid", "")  # Note: lowercase 'thingid'
        author = comment_elem.get("author", "")
        score = int(comment_elem.get("score", 0))
        depth = int(comment_elem.get("depth", 0))
        permalink = comment_elem.get("permalink", "")

        # Extract parent ID for replies
        parent_id = comment_elem.get("parentid", "")  # Note: lowercase 'parentid'

        # Also extract post ID
        post_id = comment_elem.get("postid", "")  # Note: lowercase 'postid'

        # If post_id is empty, try to extract from permalink
        if not post_id and permalink:
            # Permalink format: /r/subreddit/comments/post_id/comment/comment_id/
            parts = permalink.split("/")
            if len(parts) >= 4:
                post_id = parts[3]  # Extract post_id from permalink

        # Extract comment text
        comment_text = ""

        # Method 1: Look for div with scalable-text class (most reliable)
        scalable_divs = comment_elem.find_all(
            "div", class_="py-0 xs:mx-xs mx-2xs inline-block max-w-full scalable-text"
        )
        if scalable_divs:
            comment_text = scalable_divs[0].get_text(strip=True)

        # Method 2: Look for any div with post-rtjson-content in ID
        if not comment_text:
            all_divs = comment_elem.find_all("div")
            for div in all_divs:
                div_id = div.get("id", "")
                if "post-rtjson-content" in div_id:
                    comment_text = div.get_text(strip=True)
                    break

        # Method 3: Fallback to md text-14-scalable div
        if not comment_text:
            comment_content_div = comment_elem.find("div", class_="md text-14-scalable")
            if comment_content_div:
                content_div = comment_content_div.find(
                    "div",
                    class_="py-0 xs:mx-xs mx-2xs inline-block max-w-full scalable-text",
                )
                if content_div:
                    comment_text = content_div.get_text(strip=True)

        # Extract timestamp
        timestamp = ""
        time_elem = comment_elem.find("time")
        if time_elem:
            timestamp = time_elem.get("datetime", "")

        # Extract relative time text (e.g., "1mo ago")
        relative_time = ""
        if time_elem:
            relative_time = time_elem.get_text(strip=True)

        comment_data = {
            "comment_id": comment_id,
            # "author": author,
            "upvote": score,
            "depth": depth,
            "permalink": permalink,
            "parent_id": parent_id,  # Add parent_id for hierarchical structure
            "comment_body": comment_text,
            # "comment_date": timestamp,
            # "comment_relative_time": relative_time,
            # "post_id": post_id,
            "replies": [],  # Will be populated by the hierarchical structure
        }

        return comment_data

    except Exception as e:
        print(f"Error extracting comment data: {e}")
        return None


def save_comments_to_json(comments_data, filename="parsed_comments.json"):
    """
    Save parsed comments data to a JSON file.

    Args:
        comments_data (dict): Parsed comments data
        filename (str): Output filename
    """
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(comments_data, f, indent=2, ensure_ascii=False)
    print(f"Comments saved to {filename}")


def print_comments_summary(comments_data):
    """
    Print a summary of parsed comments.

    Args:
        comments_data (dict): Parsed comments data
    """
    print("=== Reddit Comments Parsing Results ===")
    print(f"Total Comments: {comments_data['total_comments']}")
    print(f"Comments Found: {len(comments_data['comments'])}")
    print("\n=== Comment Details ===")

    for i, comment in enumerate(comments_data["comments"], 1):
        print(f"\nComment {i}:")
        print(f"  Author: {comment['author']}")
        print(f"  Score (Upvotes): {comment['score']}")
        print(f"  Depth: {comment['depth']}")
        print(f"  Timestamp: {comment['timestamp']}")
        print(f"  Relative Time: {comment['relative_time']}")
        print(
            f"  Text: {comment['text'][:100]}..."
            if len(comment["text"]) > 100
            else f"  Text: {comment['text']}"
        )
        print(f"  Replies: {len(comment['replies'])}")

        # Show replies if any
        if comment["replies"]:
            print("  Replies:")
            for j, reply in enumerate(comment["replies"], 1):
                print(f"    Reply {j}:")
                print(f"      Author: {reply['author']}")
                print(f"      Score: {reply['score']}")
                print(
                    f"      Text: {reply['text'][:50]}..."
                    if len(reply["text"]) > 50
                    else f"      Text: {reply['text']}"
                )


def is_post_relevant(post_title, keywords):
    prompt = f"Is this post title '{post_title}' related to any of the topics of these keywords: {keywords}? Answer yes or no."
    response = client.models.generate_content(
        # model="gemini-2.5-flash",
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0)  # Disables thinking
        ),
    )
    if "yes" in response.text.lower():
        return True
    else:
        return False


def generate_comment_summary(row, comment_column):
    """
    Use Gemini API to generate summary for a comment:
    - Sentiment (one word) [element 0]
    - Misinformation (very short, or 'None') [element 1]
    - Very short summary [element 2]
    Returns: [sentiment, misinformation, summary]
    """
    try:
        # Check if the comment column is None or empty
        if (
            pd.isna(row[comment_column])
            or row[comment_column] is None
            or row[comment_column] == ""
        ):
            return ["None", "None", "None"]

        # Parse the JSON string from the comment column
        comment_data = ast.literal_eval(row[comment_column])
        comment_body = comment_data.get("comment_body", "")

        if not comment_body:
            return ["None", "None", "None"]

        prompt = (
            f"Given the following Reddit comment:\n"
            f"Comment: {comment_body}\n\n"
            "Provide three items separated by '|' (pipe symbol):\n"
            "1. What is the overall sentiment of the comment? Respond with a single word (e.g., Positive, Negative, Neutral, Angry, Hopeful, etc.).\n"
            "2. Is there any misinformation in the comment? If yes, describe it very briefly (max 15 words). If none, respond 'None'.\n"
            "3. Give a very short summary of the comment (max 15 words).\n"
            "Format: sentiment|misinformation|summary"
        )

        response = client.models.generate_content(
            # model="gemini-2.5-flash",
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            ),
        )

        # Clean the response text
        response_text = response.text.strip()

        # Split by pipe symbol to get the three components
        parts = response_text.split("|")
        if len(parts) >= 3:
            return [parts[0].strip(), parts[1].strip(), parts[2].strip()]

        # Fallback: try to extract lines if pipe splitting fails
        lines = [
            line.strip("-• \n") for line in response_text.splitlines() if line.strip()
        ]
        if len(lines) >= 3:
            return lines[:3]

        return ["None", "None", "None"]
    except Exception as e:
        print(f"Error generating summary for {comment_column}: {e}")
        return ["None", "None", "None"]


def generate_post_summary(row):
    """
    Use Gemini API to generate:
    - Sentiment (one word) [element 0]
    - Misinformation (very short, or 'None') [element 1]
    - Very short summary [element 2]
    Returns: [sentiment, misinformation, summary]
    """
    prompt = (
        f"Given the following Reddit post information:\n"
        f"Title: {row['post_title']}\n"
        f"Upvotes: {row['post_upvotes']}\n"
        f"Total Comments: {row['total_comments']}\n"
        f"Body: {row['post_body']}\n\n"
        "Provide three items separated by '|' (pipe symbol):\n"
        "1. What is the overall sentiment of the post? Respond with a single word (e.g., Positive, Negative, Neutral, Angry, Hopeful, etc.).\n"
        "2. Is there any misinformation in the post? If yes, describe it very briefly (max 15 words). If none, respond 'None'.\n"
        "3. Give a very short summary of the post (max 15 words).\n"
        "Format: sentiment|misinformation|summary"
    )
    try:
        response = client.models.generate_content(
            # model="gemini-2.5-flash",
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            ),
        )

        # Clean the response text
        response_text = response.text.strip()

        # Split by pipe symbol to get the three components
        parts = response_text.split("|")
        if len(parts) >= 3:
            return [parts[0].strip(), parts[1].strip(), parts[2].strip()]

        # Fallback: try to extract lines if pipe splitting fails
        lines = [
            line.strip("-• \n") for line in response_text.splitlines() if line.strip()
        ]
        if len(lines) >= 3:
            return lines[:3]

        return ["None", "None", "None"]
    except Exception as e:
        print(f"Error generating summary for post: {e}")
        return ["None", "None", "None"]
