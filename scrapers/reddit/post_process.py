"""
Post process the scraped data. Use gemini api to keep only relevant posts.
Then use gemini api to generate a summary of the post. (sentiment, misinformation, topic_summary)

Run using: python ./scrapers/reddit/post_process.py --input_file output/reddit/output.csv --output_file output/reddit/output_filtered.csv --keywords "keyword1,keyword2,keyword3"
"""

import argparse
import ast
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from dotenv import load_dotenv
from functions import generate_comment_summary, generate_post_summary, is_post_relevant
from google import genai
from google.genai import types


def check_relevance_concurrent(row_data, keywords_list):
    """Check relevance for a single row using ThreadPoolExecutor"""
    idx = row_data["index"]
    row = row_data["row"]

    try:
        # Call the underlying is_post_relevant function directly
        is_relevant = is_post_relevant(row["post_title"], keywords_list)
        return {"index": idx, "is_relevant": is_relevant}
    except Exception as e:
        print(f"Error checking relevance for row {idx}: {e}")
        return {"index": idx, "is_relevant": False}


load_dotenv()


client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# fmt:off
parser = argparse.ArgumentParser(description="Post process the scraped data.")
parser.add_argument("--input_file", type=str, required=True, help="The input file to process.")
parser.add_argument("--output_file", type=str, required=True, help="The output file to save the filtered data.")
parser.add_argument("--keywords", type=str, required=True, help="The keywords to filter the data by.")
args = parser.parse_args()
# fmt:on


# sanity checks
if not os.path.exists(args.input_file):
    raise FileNotFoundError(f"Input file {args.input_file} does not exist.")


# Filter out posts that are not relevant to the keywords
df = pd.read_csv(args.input_file)
print(f"Loaded {len(df)} posts from {args.input_file}")
keywords_list = [kw.strip() for kw in args.keywords.split(",") if kw.strip()]

rows_list = df.to_dict("records")
rows_data = [{"index": idx, "row": row} for idx, row in enumerate(rows_list)]
print(f"Starting relevance checking for {len(df)} posts...")
start_time = time.time()

# Use ThreadPoolExecutor for concurrent relevance checking
max_workers_relevance = 10  # Can use more workers for relevance checking
with ThreadPoolExecutor(max_workers=max_workers_relevance) as executor:
    # Submit all tasks
    future_to_idx = {
        executor.submit(check_relevance_concurrent, row_data, keywords_list): row_data[
            "index"
        ]
        for row_data in rows_data
    }
    completed_count = 0
    relevance_results = {}

    for future in as_completed(future_to_idx):
        try:
            result = future.result()
            relevance_results[result["index"]] = result["is_relevant"]
            completed_count += 1
            if completed_count % 50 == 0:
                elapsed_time = time.time() - start_time
                print(
                    f"Checked relevance for {completed_count} posts... (Elapsed: {elapsed_time:.2f}s)"
                )
        except Exception as e:
            print(f"Error processing relevance future: {e}")

relevant_indices = [
    idx for idx, is_relevant in relevance_results.items() if is_relevant
]
df = df.iloc[relevant_indices].reset_index(drop=True)

elapsed_time = time.time() - start_time
print(
    f"Filtered {len(rows_list)} posts to {len(df)} relevant posts (Time: {elapsed_time:.2f}s)"
)


# Generate a summary of the post. and top 5 comments tree
# 1. sentiment
# 2. misinformation
# 3. topic_summary

print(f"Starting summary generation for {len(df)} posts...")

# Initialize the summary columns
df["post_summary"] = ""
df["comment_1_summary"] = ""
df["comment_2_summary"] = ""
df["comment_3_summary"] = ""
df["comment_4_summary"] = ""
df["comment_5_summary"] = ""

# Convert DataFrame to list of dictionaries for easier processing
rows_list = df.to_dict("records")


def process_row_summaries(row_data):
    """Process summaries for a single row using ThreadPoolExecutor"""
    idx = row_data["index"]
    row = row_data["row"]

    try:
        post_summary = generate_post_summary(row)
        comment_1_summary = generate_comment_summary(row, "comment_1")
        comment_2_summary = generate_comment_summary(row, "comment_2")
        comment_3_summary = generate_comment_summary(row, "comment_3")
        comment_4_summary = generate_comment_summary(row, "comment_4")
        comment_5_summary = generate_comment_summary(row, "comment_5")

        return {
            "index": idx,
            "post_summary": post_summary,
            "comment_1_summary": comment_1_summary,
            "comment_2_summary": comment_2_summary,
            "comment_3_summary": comment_3_summary,
            "comment_4_summary": comment_4_summary,
            "comment_5_summary": comment_5_summary,
        }
    except Exception as e:
        print(f"Error processing row {idx}: {e}")
        return {
            "index": idx,
            "post_summary": f"Error: {e}",
            "comment_1_summary": f"Error: {e}",
            "comment_2_summary": f"Error: {e}",
            "comment_3_summary": f"Error: {e}",
            "comment_4_summary": f"Error: {e}",
            "comment_5_summary": f"Error: {e}",
        }


# Prepare data for concurrent processing
rows_data = [{"index": idx, "row": row} for idx, row in enumerate(rows_list)]

# Use ThreadPoolExecutor for concurrent processing
max_workers = 10  # Limit concurrent requests to avoid rate limiting
start_time = time.time()

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    # Submit all tasks
    future_to_idx = {
        executor.submit(process_row_summaries, row_data): row_data["index"]
        for row_data in rows_data
    }

    completed_count = 0
    for future in as_completed(future_to_idx):
        try:
            result = future.result()
            idx = result["index"]

            # Update DataFrame with results
            df.at[idx, "post_summary"] = result["post_summary"]
            df.at[idx, "comment_1_summary"] = result["comment_1_summary"]
            df.at[idx, "comment_2_summary"] = result["comment_2_summary"]
            df.at[idx, "comment_3_summary"] = result["comment_3_summary"]
            df.at[idx, "comment_4_summary"] = result["comment_4_summary"]
            df.at[idx, "comment_5_summary"] = result["comment_5_summary"]

            completed_count += 1
            if completed_count % 30 == 0:
                elapsed_time = time.time() - start_time
                print(
                    f"Generated summaries for {completed_count} posts... (Elapsed: {elapsed_time:.2f}s)"
                )

        except Exception as e:
            print(f"Error processing future: {e}")

elapsed_time = time.time() - start_time
print(
    f"Completed summary generation for all {len(df)} posts! (Total time: {elapsed_time:.2f}s)"
)

df.to_csv(args.output_file, index=False)
