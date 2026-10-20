#!/usr/bin/env python3
"""
Reddit fetching utilities for baby-arb-ke.
Provides fetch_subreddit function with multiple fallback strategies.
"""

import json
import html
import re
import requests
import time
from typing import List, Dict, Optional


def fetch_json_url(url: str) -> Optional[dict]:
    """
    Fetch a JSON URL. Try using requests with browser-like headers.
    Returns parsed JSON or None on failure.
    """
    # We'll try a couple of different User-Agents in case one is blocked
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    max_retries = 3
    for ua in user_agents:
        for attempt in range(max_retries):
            try:
                headers = {
                    'User-Agent': ua,
                    'Accept': 'application/json',
                    'Accept-Language': 'en-US,en;q=0.9',
                }
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        # Wait before retrying
                        time.sleep(2 ** attempt)  # exponential backoff
                        continue
                    else:
                        # Max retries reached for this User-Agent
                        break
                if response.status_code == 200:
                    # Reddit sometimes returns JSON wrapped in <pre> when viewed in browser
                    text = response.text
                    # If the response is HTML, try to extract <pre>
                    if text.strip().startswith('<'):
                        # Simple extraction: look for <pre> tag
                        start = text.find('<pre>')
                        end = text.find('</pre>')
                        if start != -1 and end != -1:
                            text = text[start+5:end]
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        # If still not JSON, try the next User-Agent
                        break
                else:
                    # If we get a 403, try the next User-Agent
                    if response.status_code == 403:
                        break
                    else:
                        # For other status codes, break and try next UA
                        break
            except Exception as e:
                # print(f"Error fetching {url} with requests (UA: {ua}): {e}")
                break
    return None


def fetch_via_rss(subreddit: str, limit: int = 50) -> List[Dict]:
    """
    Fetch Reddit posts via RSS feed.
    Returns list of post dicts with keys: title, selftext, score, num_comments.
    Note: RSS doesn't provide score or num_comments, so they are set to 0.
    """
    rss_url = f"https://old.reddit.com/r/{subreddit}/.rss?limit={limit}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(rss_url, headers=headers, timeout=15)
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    # Wait before retrying
                    time.sleep(2 ** attempt)  # exponential backoff
                    continue
                else:
                    # Max retries reached
                    return []
            if response.status_code == 200:
                content = response.text.strip()
                # Check if we got XML/RSS or a block page
                if content.startswith('<?xml') or '<feed' in content or '<rss' in content:
                    # print(f"Successfully fetched RSS for r/{subreddit}")
                    # Parse RSS feed to extract posts
                    import re
                    posts = []
                    # Find all entry items
                    entries = re.findall(r'<entry>(.*?)</entry>', content, re.DOTALL | re.IGNORECASE)
                    if not entries:
                        # Try alternative pattern
                        entries = re.findall(r'<item>(.*?)</item>', content, re.DOTALL | re.IGNORECASE)

                    for entry in entries[:limit]:  # Respect limit
                        # Extract title
                        title_match = re.search(r'<title>(.*?)</title>', entry, re.DOTALL | re.IGNORECASE)
                        title = title_match.group(1).strip() if title_match else ""
                        # Clean HTML entities and CDATA
                        title = re.sub(r'<!\\[CDATA\\[|]]>', '', title)
                        title = re.sub(r'&[a-z]+;', '', title)  # Simple HTML entity removal

                        # Extract content/description
                        content_match = re.search(r'<(?:content|description|summary)>(.*?)</(?:content|description|summary)>', entry, re.DOTALL | re.IGNORECASE)
                        selftext = content_match.group(1).strip() if content_match else ""
                        selftext = html.unescape(selftext)  # Unescape HTML entities
                        selftext = re.sub(r'<[^>]+>', ' ', selftext)  # Remove HTML tags
                        selftext = re.sub(r'\\s+', ' ', selftext).strip()  # Normalize whitespace

                        # Extract published date (not used in scoring but keep for completeness)
                        published_match = re.search(r'<(?:published|updated|pubDate)>(.*?)</(?:published|updated|pubDate)>', entry, re.DOTALL | re.IGNORECASE)
                        published = published_match.group(1).strip() if published_match else ""

                        # Extract link/permalink
                        link_match = re.search(r'<link[^>]*>(.*?)</link>', entry, re.DOTALL | re.IGNORECASE)
                        permalink = link_match.group(1).strip() if link_match else ""
                        # Clean up permalink to get just the Reddit path
                        permalink = re.sub(r'^https?://[^/]+', '', permalink)

                        posts.append({
                            "title": title,
                            "selftext": selftext,
                            "score": 0,  # RSS doesn't provide score
                            "num_comments": 0,  # RSS doesn't provide comment count
                        })
                    return posts
                else:
                    # print(f"Got blocked content for r/{subreddit} via RSS")
                    return []
            else:
                # print(f"HTTP {response.status_code} for r/{subreddit} RSS")
                return []
        except Exception as e:
            # print(f"Error fetching RSS for r/{subreddit}: {e}")
            return []
    # If we ran out of retries
    return []


def fetch_subreddit(subreddit: str, limit: int = 50) -> List[Dict]:
    """
    Fetch posts from a subreddit with fallback strategies.
    Order: JSON endpoint -> RSS feed -> return empty list.
    """
    # Try JSON endpoint first
    json_url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
    data = fetch_json_url(json_url)
    if data and 'data' in data and 'children' in data['data']:
        posts = data['data']['children']
        # Convert to the expected format
        result = []
        for post in posts:
            post_data = post.get('data', {})
            result.append({
                "title": post_data.get('title', ""),
                "selftext": post_data.get('selftext', ""),
                "score": post_data.get('score', 0),
                "num_comments": post_data.get('num_comments', 0),
            })
        return result

    # Fallback to RSS
    rss_posts = fetch_via_rss(subreddit, limit)
    if rss_posts:
        return rss_posts

    # If all methods fail, return empty list
    return []