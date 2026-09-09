"""
Fetch a URL and extract the main article/page text, stripping nav,
ads, and boilerplate. Uses trafilatura, which is purpose-built for
this and handles most real-world sites well; falls back to a plain
BeautifulSoup text dump if trafilatura comes back empty.
"""

# import requests
#
# _HEADERS = {
#     "User-Agent": (
#         "Mozilla/5.0 (compatible; PersonaTwinBot/1.0; "
#         "+https://example.com/bot)"
#     )
# }
#
#
# def _fallback_extract(html: str) -> str:
#     from bs4 import BeautifulSoup
#
#     soup = BeautifulSoup(html, "html.parser")
#     for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
#         tag.decompose()
#     text = soup.get_text(separator="\n")
#     lines = [line.strip() for line in text.splitlines() if line.strip()]
#     return "\n".join(lines)
#
#
# def extract_url(url: str, timeout: int = 20) -> str:
#     import trafilatura
#
#     response = requests.get(url, headers=_HEADERS, timeout=timeout)
#     response.raise_for_status()
#     html = response.text
#
#     extracted = trafilatura.extract(html, include_comments=False, include_tables=True)
#     if extracted and extracted.strip():
#         return extracted.strip()
#
#     # trafilatura found nothing useful (e.g. heavily JS-rendered page) - fall back
#     fallback = _fallback_extract(html)
#     if not fallback.strip():
#         raise ValueError(f"Could not extract any readable text from {url}")
#     return fallback

"""
Fetch a URL and extract the main article/page text.
Includes dedicated scraping for Instagram profiles via instaloader
and Twitter/X profiles via twikit.
"""

# import asyncio
# import urllib.parse
# import requests
#
# _HEADERS = {
#     "User-Agent": (
#         "Mozilla/5.0 (compatible; PersonaTwinBot/1.0; "
#         "+https://example.com/bot)"
#     )
# }
#
#
# def _extract_instagram(url: str) -> str:
#     import instaloader
#
#     parsed = urllib.parse.urlparse(url)
#     path_parts = [p for p in parsed.path.split('/') if p]
#     if not path_parts:
#         raise ValueError(f"Could not parse Instagram username from {url}")
#
#     username = path_parts[0]
#
#     L = instaloader.Instaloader(
#         download_pictures=False,
#         download_videos=False,
#         download_comments=False,
#         save_metadata=False
#     )
#
#     try:
#         L.load_session_from_file("personatwinnn")
#     except Exception as e:
#         print(f"Warning: Failed to load Instaloader session: {e}. Scraping anonymously.")
#
#     try:
#         profile = instaloader.Profile.from_username(L.context, username)
#     except Exception as e:
#         raise ValueError(f"Failed to fetch Instagram profile '{username}': {e}")
#
#     lines = [
#         f"--- INSTAGRAM PROFILE: {profile.full_name or username} (@{username}) ---",
#         f"Bio: {profile.biography or 'No bio provided.'}\n"
#     ]
#
#     try:
#         for i, post in enumerate(profile.get_posts()):
#             if i >= 15:
#                 break
#             if post.caption:
#                 lines.append(f"Post on {post.date_utc.date()}:")
#                 lines.append(f"{post.caption}\n")
#     except Exception as e:
#         lines.append(f"[Warning: Could not fetch posts due to Instagram rate limits: {e}]")
#
#     return "\n".join(lines)
#
#
# async def _fetch_twitter_data(username: str) -> str:
#     from twikit import Client
#     client = Client('en-US')
#     try:
#         client.load_cookies('twitter_cookies.json')
#     except Exception as e:
#         raise ValueError(f"Failed to load Twikit cookies (run twitter_login.py first!): {e}")
#
#     user = await client.get_user_by_screen_name(username)
#     if not user:
#         raise ValueError(f"Twitter user '{username}' not found.")
#
#     lines = [
#         f"--- TWITTER PROFILE: {user.name} (@{username}) ---",
#         f"Bio: {user.description or 'No bio provided.'}\n"
#     ]
#
#     try:
#         tweets = await client.get_user_tweets(user.id, 'Tweets')
#         count = 0
#         for tweet in tweets:
#             if count >= 20:
#                 break
#             if not tweet.text.startswith("RT @"):
#                 lines.append(f"Tweet on {tweet.created_at}:")
#                 lines.append(f"{tweet.text}\n")
#                 count += 1
#     except Exception as e:
#         lines.append(f"[Warning: Could not fetch tweets: {e}]")
#
#     return "\n".join(lines)
#
#
# def _extract_twitter(url: str) -> str:
#     parsed = urllib.parse.urlparse(url)
#     path_parts = [p for p in parsed.path.split('/') if p]
#     if not path_parts:
#         raise ValueError(f"Could not parse Twitter username from {url}")
#     username = path_parts[0]
#     return asyncio.run(_fetch_twitter_data(username))
#
#
# def _fallback_extract(html: str) -> str:
#     from bs4 import BeautifulSoup
#     soup = BeautifulSoup(html, "html.parser")
#     for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
#         tag.decompose()
#     text = soup.get_text(separator="\n")
#     lines = [line.strip() for line in text.splitlines() if line.strip()]
#     return "\n".join(lines)
#
#
# def extract_url(url: str, timeout: int = 20) -> str:
#     parsed = urllib.parse.urlparse(url)
#     domain = parsed.netloc.lower()
#
#     if "instagram.com" in domain:
#         return _extract_instagram(url)
#     if "twitter.com" in domain or "x.com" in domain:
#         return _extract_twitter(url)
#
#
#     import trafilatura
#     response = requests.get(url, headers=_HEADERS, timeout=timeout)
#     response.raise_for_status()
#     html = response.text
#
#     extracted = trafilatura.extract(html, include_comments=False, include_tables=True)
#     if extracted and extracted.strip():
#         return extracted.strip()
#
#     fallback = _fallback_extract(html)
#     if not fallback.strip():
#         raise ValueError(f"Could not extract any readable text from {url}")
#     return fallback
#

"""
Fetch a URL and extract the main article/page text.
Includes dedicated scraping for Instagram profiles (instaloader),
Twitter/X profiles (twikit), and LinkedIn profiles (playwright).
"""

import asyncio
import urllib.parse
import requests

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; PersonaTwinBot/1.0; "
        "+https://example.com/bot)"
    )
}


def _extract_instagram(url: str) -> str:
    import json
    import time
    from playwright.sync_api import sync_playwright

    parsed = urllib.parse.urlparse(url)
    path_parts = [p for p in parsed.path.split('/') if p]
    if not path_parts:
        raise ValueError(f"Could not parse Instagram username from {url}")

    username = path_parts[0]
    lines = [f"--- INSTAGRAM PROFILE: @{username} ---"]

    with sync_playwright() as p:
        # Headless=False helps avoid bot detection on IG
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent=_HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 800}
        )

        try:
            with open('instagram_cookies.json', 'r', encoding='utf-8') as f:
                raw_cookies = json.load(f)
                valid_cookies = []
                for c in raw_cookies:
                    # Clean up cookie dicts for playwright
                    cookie = {
                        "name": c["name"],
                        "value": c["value"],
                        "domain": c["domain"],
                        "path": c.get("path", "/")
                    }
                    if "sameSite" in c and c["sameSite"] in ["Strict", "Lax", "None"]:
                        cookie["sameSite"] = c["sameSite"]
                    valid_cookies.append(cookie)
                
                context.add_cookies(valid_cookies)
        except Exception as e:
            print(f"Warning: Failed to load instagram_cookies.json for Playwright: {e}")

        page = context.new_page()
        print(f"Loading Instagram profile for {username}...")
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Wait a moment for React to render
            time.sleep(3)
            
            # 1. Try to extract header (Bio, stats, name)
            try:
                header = page.locator("header")
                header.wait_for(timeout=5000)
                lines.append(f"Header / Bio:\n{header.inner_text()}\n")
            except:
                lines.append("Bio: Could not extract header.")
                
            # 2. Try to extract post captions from the image grid's alt text
            try:
                # Wait for post links instead of just 'article', which changes often
                # A post URL on instagram usually contains /p/
                page.wait_for_selector("a[href*='/p/']", timeout=15000)
                images = page.locator("a[href*='/p/'] img").all()
                
                # Fallback if no images found inside /p/ links
                if not images:
                    images = page.locator("article img").all()
                
                if not images:
                    images = page.locator("main img").all()

                lines.append("--- RECENT POSTS ---")
                count = 0
                for img in images:
                    if count >= 15:
                        break
                    alt = img.get_attribute("alt")
                    # Filter out profile pic or empty alts
                    if alt and "profile picture" not in alt.lower():
                        lines.append(f"Post Snippet:\n{alt}\n")
                        count += 1
            except Exception as e:
                page.screenshot(path="ig_error.png")
                lines.append(f"[Warning: Could not fetch posts from grid. Saved screenshot to ig_error.png. Error: {e}]")
                
        except Exception as e:
             lines.append(f"[Error loading profile: {e}]")
        finally:
            browser.close()

    return "\n".join(lines)


async def _fetch_twitter_data(username: str) -> str:
    from twikit import Client
    client = Client('en-US')
    try:
        client.load_cookies('twitter_cookies.json')
    except Exception as e:
        raise ValueError(f"Failed to load Twikit cookies: {e}")

    user = await client.get_user_by_screen_name(username)
    if not user:
        raise ValueError(f"Twitter user '{username}' not found.")

    lines = [
        f"--- TWITTER PROFILE: {user.name} (@{username}) ---",
        f"Bio: {user.description or 'No bio provided.'}\n"
    ]

    try:
        tweets = await client.get_user_tweets(user.id, 'Tweets')
        count = 0
        for tweet in tweets:
            if count >= 20:
                break
            if not tweet.text.startswith("RT @"):
                lines.append(f"Tweet on {tweet.created_at}:")
                lines.append(f"{tweet.text}\n")
                count += 1
    except Exception as e:
        lines.append(f"[Warning: Could not fetch tweets: {e}]")

    return "\n".join(lines)


def _extract_twitter(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    path_parts = [p for p in parsed.path.split('/') if p]
    if not path_parts:
        raise ValueError(f"Could not parse Twitter username from {url}")
    username = path_parts[0]
    return asyncio.run(_fetch_twitter_data(username))


def _fallback_extract(html: str) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def extract_url(url: str, timeout: int = 20) -> str:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()

    if "instagram.com" in domain:
        return _extract_instagram(url)
    if "twitter.com" in domain or "x.com" in domain:
        return _extract_twitter(url)


    import trafilatura
    response = requests.get(url, headers=_HEADERS, timeout=timeout)
    response.raise_for_status()
    html = response.text

    extracted = trafilatura.extract(html, include_comments=False, include_tables=True)
    if extracted and extracted.strip():
        return extracted.strip()

    fallback = _fallback_extract(html)
    if not fallback.strip():
        raise ValueError(f"Could not extract any readable text from {url}")
    return fallback