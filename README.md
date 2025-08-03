# Digital Rupee Reddit Analysis Tool

A comprehensive tool for scraping, analyzing, and visualizing Reddit discussions about Digital Rupee (e₹) and related topics using Scrapy, Google Gemini AI, and Streamlit.

## Features

- **Automated Reddit Scraping**: Collects posts and comments from Reddit using authenticated sessions
- **AI-Powered Analysis**: Uses Google Gemini AI to analyze sentiment, detect misinformation, and generate summaries
- **Interactive Dashboard**: Streamlit web application for data visualization and exploration
- **Concurrent Processing**: Optimized for high-performance data processing
- **Resume Capability**: Can resume scraping from where it left off

## Prerequisites

- Python 3.8+
- Reddit account credentials
- Google Gemini API key
- VPN (recommended for Reddit access)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd reddit-data-dashboard
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright and Chromium**
   ```bash
   playwright install chromium
   ```

5. **Set up environment variables**
   Create a `.env` file in the project root:
   ```bash
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

## Usage

### Step 1: Reddit Data Scraping

Scrape Reddit posts and comments related to Digital Rupee topics:

```bash
python ./scrapers/reddit/posts_and_comments.py \
  --username 'your_reddit_username' \
  --password 'your_reddit_password' \
  --storage_state './tmp/sessions/' \
  --outdir ./output/reddit/ \
  --keywords "digital rupee, e₹, e-Rupee, Central Bank Digital Currency (CBDC), digital token rupee"
```

**Parameters:**
- `--username`: Your Reddit username
- `--password`: Your Reddit password
- `--storage_state`: Directory to store session cookies
- `--outdir`: Output directory for CSV files
- `--keywords`: Comma-separated keywords to search for

### Resume Scraping

If the scraping process is interrupted, you can resume by running the same command. The scraper will:
- Load existing posts from the CSV file
- Skip already scraped posts
- Continue from where it left off

**Output:** `./output/reddit/output.csv`

### Step 2: AI-Powered Data Processing

Process scraped data using Google Gemini AI for sentiment analysis, misinformation detection, and summarization:

```bash
python ./scrapers/reddit/post_process.py \
  --input_file 'output/reddit/output.csv' \
  --output_file 'output/reddit/output_processed.csv' \
  --keywords 'digital rupee, e₹, e-Rupee, e₹-R, Central Bank Digital Currency (CBDC), Electronic money, digital token rupee'
```

**What this step does:**
- Filters posts for relevance to specified keywords
- Analyzes sentiment of posts and comments
- Detects potential misinformation
- Generates concise summaries
- Processes data concurrently for better performance

**Output:** `./output/reddit/output_processed.csv`

### Step 3: Interactive Dashboard

Launch the Streamlit dashboard to explore and visualize the processed data:

```bash
streamlit run app.py
```

The dashboard will be available at `http://localhost:8501`

## Project Structure

```
digirupe/
├── scrapers/
│   └── reddit/
│       ├── posts_and_comments.py    # Reddit scraping spider
│       ├── post_process.py          # AI processing script
│       └── functions.py             # Utility functions
├── output/
│   └── reddit/                      # Output CSV files
├── app.py                           # Streamlit dashboard
├── requirements.txt                 # Python dependencies
└── README.md                       # This file
```

## Configuration

### Reddit Scraping Settings

The scraper can be configured by modifying these parameters in `posts_and_comments.py`:

- `SCROLL_LIMIT`: Number of times to scroll to scrape per search result (default: 40)
- `SEARCH_FILTERS`: Reddit search filters (relevance, hot, top, new)
- `CONCURRENT_REQUESTS`: Number of concurrent requests (default: 20)

### AI Processing Settings

In `post_process.py`, you can adjust:

- `max_workers_relevance`: Concurrent workers for relevance checking (default: 10)
- `max_workers`: Concurrent workers for summary generation (default: 5)

## Output Data Format

The processed CSV file contains the following columns:

- **Post Information**: `post_title`, `post_url`, `subreddit`, `post_date`, `post_upvotes`, `total_comments`, `post_body`
- **Comments**: `comment_1` through `comment_5` (top comments with full reply trees, as json strings)
- **AI Analysis**: 
  - `post_summary`: [sentiment, misinformation, summary]
  - `comment_X_summary`: [sentiment, misinformation, summary] for each comment
- **Metadata**: `scraped_at` timestamp

## Troubleshooting

### Common Issues

1. **Reddit Login Failures**
   - Ensure your Reddit credentials are correct
   - Try using a VPN if you're experiencing access issues
   - Check if your account has 2FA enabled. The login script only works for username password login.

2. **Gemini API Errors**
   - Verify your API key is correct and has sufficient quota
   - Check the API key is properly set in the `.env` file

3. **API Rate Limiting**
   - Reduce `CONCURRENT_REQUESTS` in the scraper settings
   - Add delays between requests if needed


## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is for educational and research purposes only. Please respect Reddit's Terms of Service and API usage guidelines. The authors are not responsible for any misuse of this tool.


