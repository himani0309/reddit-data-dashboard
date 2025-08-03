"""
Code to login to reddit and save session cookies and headers to a location.

Run using:
  python ./scrapers/reddit/getcookies.py --username abcd --password 123456 --storage-file ./tmp/hs/storage_state.json
"""

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import requests
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

# Constants
LOGIN_URL = "https://www.reddit.com/login/"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"


CUSTOM_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "en-US,en;q=0.9",
    "dnt": "1",
    "priority": "u=0, i",
    "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": USER_AGENT,
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Playwright login helper for ODP Business"
    )
    parser.add_argument("--username", required=True, help="Login username")
    parser.add_argument("--password", required=True, help="Login password")
    parser.add_argument(
        "--storage-file",
        required=True,
        help="Path to output JSON file where storage state (cookies & headers) will be saved. Can be a local path (e.g., './tmp/hs/storage_state.json')",
    )
    return parser.parse_args()


async def login(page, context, username, password, storage_file):

    await page.locator("#login-username span").filter(has_text="*").first.click()
    await page.get_by_role("textbox", name="Email or username").click()
    await page.get_by_role("textbox", name="Email or username").fill(username)
    await page.get_by_role("textbox", name="Password").click()
    await page.get_by_role("textbox", name="Password").fill(password)
    await page.get_by_role("button", name="Log In").click()

    await page.wait_for_timeout(10_000)
    if "Invalid username or password" in await page.content():
        raise Exception(f"Login failed. Invalid username/password")

    print("Login successful ✅")

    storage_path = Path(storage_file)
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    # Save storage state (cookies, localStorage, sessionStorage)
    await asyncio.sleep(1)
    storage_state_dict = await page.context.storage_state()
    storage_state_dict["headers"] = CUSTOM_HEADERS
    with open(storage_file, "w", encoding="utf-8") as f:
        json.dump(storage_state_dict, f, indent=2)
    print(f"✓ Login complete, state saved: {storage_file}")


async def main():
    args = parse_args()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False, args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080},
            bypass_csp=True,
        )
        page = await context.new_page()

        try:
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
        except PlaywrightTimeoutError:
            print("Navigation timed out; will wait for the form instead.")

        await login(page, context, args.username, args.password, args.storage_file)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
