"""
Transform Layer (Dynamic Discovery + Optional Etsy Enrichment)
==============================================================
- Filters trademark risks using trademark_blacklist.txt
- Ranks dynamically discovered Google Trends keywords (no fake numbers!)
- Enriches with real Etsy competition/price/tags when ETSY_API_KEY is active
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ETSY_MAX_TAG_LEN = 20


def load_blacklist(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line.strip().lower()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def has_trademark(text: str, blacklist: list[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in blacklist)


def transform_data(
    extracted: dict,
    blacklist_path: Path,
    run_date: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    run_date = run_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    blacklist = load_blacklist(blacklist_path)

    trend_keywords = extracted.get("trend_keywords", [])
    etsy_listings = extracted.get("etsy_listings", [])

    # Build Etsy lookup if live Etsy data is present
    etsy_by_kw: dict[str, dict] = {}
    winning_tags_rows: list[dict] = []

    if etsy_listings:
        edf = pd.DataFrame(etsy_listings)
        edf["tags_joined"] = edf["tags"].apply(lambda t: " ".join(t) if isinstance(t, list) else str(t))
        edf = edf[~edf.apply(lambda r: has_trademark(f"{r['title']} {r['tags_joined']}", blacklist), axis=1)]

        now_ts = datetime.now(timezone.utc).timestamp()
        edf["age_days"] = ((now_ts - edf["creation_timestamp"]) / 86400.0).clip(lower=1.0)
        edf["is_fresh_winner"] = (edf["age_days"] < 90) & (edf["num_favorers"] >= 30)

        for kw, grp in edf.groupby("keyword"):
            etsy_by_kw[kw] = {
                "total_competition": int(grp["total_competition"].max()),
                "avg_price_usd": round(float(grp["price_usd"].mean()), 2),
                "fresh_winners_count": int(grp["is_fresh_winner"].sum()),
            }

        tags_df = edf[["keyword", "tags"]].explode("tags").dropna(subset=["tags"])
        tags_df["tag"] = tags_df["tags"].astype(str).str.strip().str.lower()
        tags_df = tags_df[
            (tags_df["tag"].str.len() > 0)
            & (tags_df["tag"].str.len() <= ETSY_MAX_TAG_LEN)
            & (~tags_df["tag"].apply(lambda t: has_trademark(t, blacklist)))
        ]
        wt = (
            tags_df.groupby(["keyword", "tag"])
            .size()
            .reset_index(name="frequency")
            .sort_values(["keyword", "frequency"], ascending=[True, False])
            .groupby("keyword", as_index=False)
            .head(13)
        )
        wt.rename(columns={"keyword": "niche"}, inplace=True)
        wt.insert(0, "date", run_date)
        winning_tags_rows = wt.to_dict(orient="records")

    scorecard_rows = []
    for item in trend_keywords:
        kw = item["keyword"]
        if has_trademark(kw, blacklist):
            continue

        growth = int(item.get("growth_pct", 0))
        t_type = item.get("trend_type", "RISING")
        seed = item.get("seed_category", "")

        # Pure real-data score: Google Trends momentum + Etsy data (if available)
        trend_pts = min(growth / 5.0, 60.0) if t_type == "RISING" else min(growth * 0.4, 40.0)
        etsy_info = etsy_by_kw.get(kw)
        if etsy_info:
            comp = etsy_info["total_competition"]
            price = etsy_info["avg_price_usd"]
            fresh = etsy_info["fresh_winners_count"]
            etsy_pts = (20.0 if 1000 <= comp <= 15000 else 8.0) + (10.0 if price >= 24 else 4.0) + min(fresh * 2.0, 10.0)
            opp_score = round(min(trend_pts + etsy_pts, 100.0), 1)
        else:
            comp = None
            price = None
            fresh = None
            opp_score = round(min(trend_pts * 1.5, 100.0), 1)

        scorecard_rows.append({
            "date": run_date,
            "niche": kw,
            "seed_category": seed,
            "trend_type": t_type,
            "growth_pct": growth,
            "total_competition": comp if comp is not None else "Pending Etsy API",
            "avg_price_usd": price if price is not None else "Pending Etsy API",
            "fresh_winners_count": fresh if fresh is not None else "Pending Etsy API",
            "opportunity_score": opp_score,
        })

    scorecard_df = pd.DataFrame(scorecard_rows)
    if not scorecard_df.empty:
        scorecard_df = scorecard_df.sort_values(by=["opportunity_score", "growth_pct"], ascending=False)

    winning_tags_df = pd.DataFrame(winning_tags_rows)
    return scorecard_df, winning_tags_df
