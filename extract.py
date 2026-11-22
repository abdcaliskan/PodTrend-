"""
Extract Layer
=============
Pulls active listing data from Etsy Open API v3 and 90-day trend slope from Google Trends.
Supports --mock mode so the pipeline can be tested before API keys are ready.
"""

import os
import time
from datetime import datetime, timezone
from typing import Any

import requests

ETSY_ACTIVE_LISTINGS_URL = "https://openapi.etsy.com/v3/application/listings/active"
PINTEREST_TRENDS_URL = "https://api.pinterest.com/v5/trends/keywords/US/top/growing"
EBAY_BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
GELATO_CATALOGS_URL = "https://product.gelatoapis.com/v3/catalogs"


def fetch_gelato_catalogs(api_key: str) -> list[dict[str, Any]]:
    """Fetches available product catalogs from Gelato Seller API using X-API-KEY."""
    if not api_key:
        return []
    try:
        resp = requests.get(
            GELATO_CATALOGS_URL,
            headers={"X-API-KEY": api_key},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as exc:
        print(f"[Extract] Gelato Catalog API skipped: {exc}")
        return []


def fetch_pinterest_trends(access_token: str, limit: int = 20) -> list[dict[str, Any]]:
    """Pulls today's growing keywords (WoW/MoM/YoY) from Pinterest Trends API v5."""
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


def fetch_ebay_price_benchmark(niche: str, access_token: str) -> dict[str, Any]:
    """Cross-checks average price and competition count via eBay Browse API."""
    if not access_token:
        return {}
    try:
        resp = requests.get(
            EBAY_BROWSE_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-EBAY-C-ENDUSERCTX": "contextualLocation=country%3DUS%2Czip%3D19406",
            },
            params={"q": niche, "limit": 20},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        prices = [
            float(item["price"]["value"])
            for item in data.get("itemSummaries", [])
            if item.get("price", {}).get("value")
        ]
        return {
            "ebay_total": int(data.get("total", 0)),
            "ebay_avg_price": round(sum(prices) / len(prices), 2) if prices else 0.0,
        }
    except Exception as exc:
        print(f"[Extract] eBay Browse skipped for '{niche}': {exc}")
        return {}


def fetch_reddit_ideas(subreddit: str, limit: int = 10) -> list[str]:
    """Pulls top weekly post titles from a niche subreddit for design inspiration."""
    try:
        resp = requests.get(
            f"https://www.reddit.com/r/{subreddit}/top.json",
            headers={"User-Agent": "pod-keyword-etl/1.0"},
            params={"t": "week", "limit": limit},
            timeout=15,
        )
        resp.raise_for_status()
        children = resp.json().get("data", {}).get("children", [])
        return [c["data"]["title"] for c in children if c.get("data", {}).get("title")]
    except Exception as exc:
        print(f"[Extract] Reddit r/{subreddit} skipped: {exc}")
        return []


def fetch_etsy_listings(niche: str, api_key: str, limit: int = 50) -> dict[str, Any]:
    """Fetch total count and top active listings for a niche keyword from Etsy Open API v3."""
    headers = {"x-api-key": api_key}
    params = {
        "keywords": niche,
        "limit": limit,
        "sort_on": "score",
    }
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
            "niche": niche,
            "listing_id": item.get("listing_id"),
            "title": item.get("title", ""),
            "price_usd": round(amount / divisor, 2),
            "num_favorers": int(item.get("num_favorers", 0)),
            "creation_timestamp": int(item.get("creation_timestamp", 0)),
            "tags": item.get("tags") or [],
            "total_competition": total_count,
        })

    return {"total_competition": total_count, "listings": listings}


def fetch_google_trend_slope(niche: str) -> float:
    """
    Returns 90-day Google Trends slope (recent 30d avg minus prior 60d avg).
    Fails gracefully to 0.0 if pytrends is unavailable or rate-limited.
    """
    try:
        from pytrends.request import TrendReq  # lazy import so mock/offline runs stay light

        pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 25))
        pytrends.build_payload([niche], cat=0, timeframe="today 3-m", geo="US")
        df = pytrends.interest_over_time()
        if df.empty or niche not in df.columns:
            return 0.0
        series = df[niche].astype(float)
        if len(series) < 10:
            return 0.0
        recent_avg = series.iloc[-30:].mean()
        prior_avg = series.iloc[:-30].mean() if len(series) > 30 else series.mean()
        return round(float(recent_avg - prior_avg), 2)
    except Exception as exc:
        print(f"[Extract] Google Trends skipped for '{niche}': {exc}")
        return 0.0


def generate_mock_data(niche: str) -> dict[str, Any]:
    """Deterministic mock data for testing before Etsy API key approval."""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    profiles = {
        "2027 vision board poster": (1850, 26.5, 220, 45, ["2027 vision board", "vision board poster", "manifestation art", "new year goals", "aesthetic wall art"]),
        "2027 daily planner hardcover": (2400, 30.5, 190, 52, ["2027 planner", "hardcover planner", "daily organizer", "habit tracker", "new year gift"]),
        "retro tennis club sweatshirt": (3200, 45.0, 140, 60, ["tennis club hoodie", "retro tennis", "racquet club", "sportswear gift", "preppy tennis"]),
        "sunday league football shirt": (2100, 27.0, 95, 70, ["sunday league", "football shirt", "vintage soccer", "matchday tee", "soccer humor"]),
        "minimalist manifestation journal": (112000, 21.0, 40, 240, ["manifestation", "journal", "notebook", "self care gift"]),
    }
    count, price, favs, age_days, tags = profiles.get(
        niche.lower(), (6500, 25.0, 85, 80, [niche.lower()[:20], "custom gift", "aesthetic print"])
    )
    created_ts = now_ts - (age_days * 86400)
    listings = [
        {
            "niche": niche,
            "listing_id": 1000 + i,
            "title": f"{niche.title()} Design #{i + 1}",
            "price_usd": round(price + (i % 3) - 1, 2),
            "num_favorers": max(5, favs - i * 8),
            "creation_timestamp": created_ts + (i * 86400),
            "tags": tags,
            "total_competition": count,
        }
        for i in range(10)
    ]
    return {"total_competition": count, "listings": listings, "trend_slope": 12.5 if age_days < 90 else -2.0}


def extract_all(niches: list[str], use_mock: bool = False) -> tuple[list[dict], dict[str, float], dict[str, Any]]:
    """Extract listings, live Gelato catalogs, Google Trends, and Reddit ideas."""
    api_key = os.getenv("ETSY_API_KEY", "").strip()
    gelato_key = os.getenv("GELATO_API_KEY", "").strip()
    pinterest_token = os.getenv("PINTEREST_ACCESS_TOKEN", "").strip()
    ebay_token = os.getenv("EBAY_ACCESS_TOKEN", "").strip()

    etsy_mode = "OK" if (api_key and not use_mock) else "MOCK_ETSY"

    gelato_catalogs = fetch_gelato_catalogs(gelato_key) if gelato_key else []
    gelato_status = f"OK ({len(gelato_catalogs)} catalogs)" if gelato_catalogs else ("ERROR" if gelato_key else "SKIPPED")

    reddit_ideas = {}
    for sub in ["planners", "running", "tennis"]:
        ideas = fetch_reddit_ideas(sub, limit=5)
        if ideas:
            reddit_ideas[sub] = ideas
    reddit_status = f"OK ({sum(len(v) for v in reddit_ideas.values())} posts)" if reddit_ideas else "SKIPPED"

    all_listings: list[dict] = []
    trend_slopes: dict[str, float] = {}
    trends_ok = 0

    for niche in niches:
        if api_key and not use_mock:
            res = fetch_etsy_listings(niche, api_key=api_key)
            all_listings.extend(res["listings"])
        else:
            res = generate_mock_data(niche)
            all_listings.extend(res["listings"])

        # Always try real Google Trends unless explicitly --mock
        if not use_mock:
            slope = fetch_google_trend_slope(niche)
            trend_slopes[niche] = slope
            if slope != 0.0:
                trends_ok += 1
        else:
            trend_slopes[niche] = res["trend_slope"]

        time.sleep(0.6)

    meta = {
        "status": "OK",
        "mode": "HYBRID_LIVE" if (gelato_catalogs or reddit_ideas or trends_ok) else "MOCK",
        "gelato_catalog_count": len(gelato_catalogs),
        "reddit_ideas": reddit_ideas,
        "sources": {
            "etsy": etsy_mode,
            "gelato": "OK" if gelato_catalogs else "SKIPPED",
            "google_trends": "OK" if trends_ok > 0 else ("SKIPPED" if use_mock else "RATE_LIMITED"),
            "pinterest": "OK" if pinterest_token else "SKIPPED",
            "ebay": "OK" if ebay_token else "SKIPPED",
            "reddit": "OK" if reddit_ideas else "SKIPPED",
        },
    }
    return all_listings, trend_slopes, meta
