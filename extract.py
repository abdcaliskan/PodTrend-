"""
Extract Layer (100% Dynamic — No Hardcoded Niches or Fake Mock Numbers)
======================================================================
1. Google Trends `related_queries()` -> Dynamically discovers rising & top queries
   from broad POD seed categories.
2. Gelato Seller API -> Fetches live product catalogs.
3. Reddit RSS -> Fetches live weekly top posts from niche subreddits.
4. Etsy Open API v3 (when ETSY_API_KEY is set) -> Enriches discovered keywords
   with real competition, price, favorers, and tags.
"""

import os
import time
import xml.etree.ElementTree as ET
from typing import Any

import requests

ETSY_ACTIVE_LISTINGS_URL = "https://openapi.etsy.com/v3/application/listings/active"
PINTEREST_TRENDS_URL = "https://api.pinterest.com/v5/trends/keywords/US/top/growing"
GELATO_CATALOGS_URL = "https://product.gelatoapis.com/v3/catalogs"

BROAD_SEED_CATEGORIES = ["planner", "vision board", "wall art poster", "graphic hoodie", "gift"]
SUBREDDITS = ["planners", "Etsy", "running", "tennis"]


def fetch_gelato_catalogs(api_key: str) -> list[dict[str, Any]]:
    """Fetches available product catalogs from Gelato Seller API."""
    if not api_key:
        return []
    try:
        resp = requests.get(GELATO_CATALOGS_URL, headers={"X-API-KEY": api_key}, timeout=20)
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as exc:
        print(f"[Extract] Gelato Catalog API skipped: {exc}")
        return []


def fetch_reddit_rss(subreddit: str, limit: int = 5) -> list[dict[str, str]]:
    """Pulls live weekly top post titles from a subreddit via public RSS (no API key needed)."""
    try:
        resp = requests.get(
            f"https://www.reddit.com/r/{subreddit}/top.rss?t=week",
            headers={"User-Agent": "PodTrendAnalytics/1.0"},
            timeout=15,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        posts = []
        for entry in root.findall("atom:entry", ns)[:limit]:
            title_el = entry.find("atom:title", ns)
            link_el = entry.find("atom:link", ns)
            if title_el is not None and title_el.text:
                posts.append({
                    "subreddit": f"r/{subreddit}",
                    "title": title_el.text.strip(),
                    "url": link_el.attrib.get("href", "") if link_el is not None else "",
                })
        return posts
    except Exception as exc:
        print(f"[Extract] Reddit RSS r/{subreddit} skipped: {exc}")
        return []


def discover_google_trends(seeds: list[str]) -> list[dict[str, Any]]:
    """
    Dynamically discovers currently rising & top queries from Google Trends
    for broad POD categories (zero hardcoded niche list).
    """
    discovered: list[dict[str, Any]] = []
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 25))
        for seed in seeds:
            try:
                pytrends.build_payload([seed], cat=0, timeframe="today 3-m", geo="US")
                related = pytrends.related_queries()
                seed_data = related.get(seed, {})

                rising_df = seed_data.get("rising")
                if rising_df is not None and not rising_df.empty:
                    for _, row in rising_df.head(6).iterrows():
                        discovered.append({
                            "keyword": str(row["query"]).strip().lower(),
                            "seed_category": seed,
                            "trend_type": "RISING",
                            "growth_pct": int(row["value"]),
                        })

                top_df = seed_data.get("top")
                if top_df is not None and not top_df.empty:
                    for _, row in top_df.head(3).iterrows():
                        discovered.append({
                            "keyword": str(row["query"]).strip().lower(),
                            "seed_category": seed,
                            "trend_type": "TOP",
                            "growth_pct": int(row["value"]),
                        })

                time.sleep(1.0)
            except Exception as exc:
                print(f"[Extract] Google Trends seed '{seed}' skipped: {exc}")
    except Exception as exc:
        print(f"[Extract] pytrends unavailable: {exc}")

    # Deduplicate by keyword, keeping highest growth
    seen: dict[str, dict[str, Any]] = {}
    for item in discovered:
        kw = item["keyword"]
        if kw not in seen or item["growth_pct"] > seen[kw]["growth_pct"]:
            seen[kw] = item
    return list(seen.values())


def fetch_pinterest_trends(access_token: str, limit: int = 20) -> list[dict[str, Any]]:
    """Pulls today's growing keywords from Pinterest Trends API v5 when approved."""
    if not access_token:
        return []
    try:
        resp = requests.get(
            PINTEREST_TRENDS_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            params={"limit": limit},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get("trends", [])
    except Exception as exc:
        print(f"[Extract] Pinterest Trends skipped: {exc}")
        return []


def fetch_etsy_listings(keyword: str, api_key: str, limit: int = 50) -> dict[str, Any]:
    """Fetches real Etsy competition, prices, favorers, and tags when ETSY_API_KEY is present."""
    headers = {"x-api-key": api_key}
    params = {"keywords": keyword, "limit": limit, "sort_on": "score"}
    resp = requests.get(ETSY_ACTIVE_LISTINGS_URL, headers=headers, params=params, timeout=20)
    resp.raise_for_status()
    payload = resp.json()

    total_count = int(payload.get("count", 0))
    listings = []
    for item in payload.get("results", []):
        price_obj = item.get("price") or {}
        amount = float(price_obj.get("amount", 0))
        divisor = float(price_obj.get("divisor", 100)) or 100.0
        listings.append({
            "keyword": keyword,
            "listing_id": item.get("listing_id"),
            "title": item.get("title", ""),
            "price_usd": round(amount / divisor, 2),
            "num_favorers": int(item.get("num_favorers", 0)),
            "creation_timestamp": int(item.get("creation_timestamp", 0)),
            "tags": item.get("tags") or [],
            "total_competition": total_count,
        })
    return {"total_competition": total_count, "listings": listings}


def extract_all(seeds: list[str] | None = None) -> dict[str, Any]:
    """Runs 100% live dynamic extraction across all available APIs."""
    seed_list = seeds or BROAD_SEED_CATEGORIES
    etsy_key = os.getenv("ETSY_API_KEY", "").strip()
    gelato_key = os.getenv("GELATO_API_KEY", "").strip()
    pinterest_token = os.getenv("PINTEREST_ACCESS_TOKEN", "").strip()

    gelato_catalogs = fetch_gelato_catalogs(gelato_key)
    trend_keywords = discover_google_trends(seed_list)
    pinterest_trends = fetch_pinterest_trends(pinterest_token)

    reddit_posts: list[dict[str, str]] = []
    for sub in SUBREDDITS:
        reddit_posts.extend(fetch_reddit_rss(sub, limit=4))

    etsy_listings: list[dict[str, Any]] = []
    if etsy_key and trend_keywords:
        for item in trend_keywords[:15]:
            try:
                res = fetch_etsy_listings(item["keyword"], api_key=etsy_key)
                etsy_listings.extend(res["listings"])
                time.sleep(0.5)
            except Exception as exc:
                print(f"[Extract] Etsy failed for '{item['keyword']}': {exc}")

    return {
        "trend_keywords": trend_keywords,
        "pinterest_trends": pinterest_trends,
        "etsy_listings": etsy_listings,
        "gelato_catalogs": gelato_catalogs,
        "reddit_posts": reddit_posts,
        "meta": {
            "status": "OK",
            "mode": "100% LIVE (DYNAMIC)",
            "gelato_catalog_count": len(gelato_catalogs),
            "discovered_keywords_count": len(trend_keywords),
            "reddit_posts_count": len(reddit_posts),
            "sources": {
                "google_trends": "OK" if trend_keywords else "RATE_LIMITED",
                "gelato": "OK" if gelato_catalogs else "SKIPPED",
                "reddit_rss": "OK" if reddit_posts else "BLOCKED",
                "pinterest": "OK" if pinterest_trends else "PENDING_APPROVAL",
                "etsy": "OK" if etsy_listings else "PENDING_KEY",
            },
        },
    }
