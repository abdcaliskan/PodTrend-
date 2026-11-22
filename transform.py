"""
Transform Layer
===============
- Filters trademark risks using trademark_blacklist.txt
- Calculates Opportunity Score (0-100) per niche
- Explodes tags across top 50 listings to produce Winning_Tags
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


def score_competition(total_count: int) -> float:
    """1,000 - 15,000 band gets full 35 pts; 100,000+ gets heavy penalty."""
    if 1_000 <= total_count <= 15_000:
        return 35.0
    if total_count < 1_000:
        return 22.0  # very low volume niche
    if total_count <= 50_000:
        return 20.0
    if total_count <= 100_000:
        return 10.0
    return 2.0


def transform_data(
    raw_listings: list[dict],
    trend_slopes: dict[str, float],
    blacklist_path: Path,
    run_date: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    run_date = run_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    blacklist = load_blacklist(blacklist_path)

    df = pd.DataFrame(raw_listings)
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Filter out listings with trademarked titles or tags
    df["tags_joined"] = df["tags"].apply(lambda t: " ".join(t) if isinstance(t, list) else str(t))
    mask_safe = ~df.apply(
        lambda r: has_trademark(f"{r['title']} {r['tags_joined']}", blacklist), axis=1
    )
    df = df[mask_safe].copy()
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    now_ts = datetime.now(timezone.utc).timestamp()
    df["age_days"] = ((now_ts - df["creation_timestamp"]) / 86400.0).clip(lower=1.0)
    df["is_fresh_winner"] = (df["age_days"] < 90) & (df["num_favorers"] >= 30)

    # 1. Niche_Scorecard
    scorecard_rows = []
    for niche, group in df.groupby("niche"):
        total_comp = int(group["total_competition"].max())
        avg_price = round(float(group["price_usd"].mean()), 2)
        fresh_winners = int(group["is_fresh_winner"].sum())
        trend_slope = float(trend_slopes.get(niche, 0.0))

        comp_pts = score_competition(total_comp)  # max 35
        velocity_pts = min(fresh_winners * 5.0, 30.0)  # max 30
        margin_pts = 20.0 if avg_price >= 24.0 else max(0.0, (avg_price / 24.0) * 15.0)  # max 20
        trend_pts = min(max(trend_slope, 0.0) * 1.0, 15.0)  # max 15

        opp_score = round(min(comp_pts + velocity_pts + margin_pts + trend_pts, 100.0), 1)

        scorecard_rows.append({
            "date": run_date,
            "niche": niche,
            "total_competition": total_comp,
            "avg_price_usd": avg_price,
            "trend_slope_90d": trend_slope,
            "fresh_winners_count": fresh_winners,
            "opportunity_score": opp_score,
        })

    scorecard_df = pd.DataFrame(scorecard_rows).sort_values(
        by="opportunity_score", ascending=False
    )

    # 2. Winning_Tags (explode tags, filter <= 20 chars & blacklist, count frequency)
    tags_df = df[["niche", "tags"]].explode("tags").dropna(subset=["tags"])
    tags_df["tag"] = tags_df["tags"].astype(str).str.strip().str.lower()
    tags_df = tags_df[
        (tags_df["tag"].str.len() > 0)
        & (tags_df["tag"].str.len() <= ETSY_MAX_TAG_LEN)
        & (~tags_df["tag"].apply(lambda t: has_trademark(t, blacklist)))
    ]

    winning_tags_df = (
        tags_df.groupby(["niche", "tag"])
        .size()
        .reset_index(name="frequency")
        .sort_values(by=["niche", "frequency"], ascending=[True, False])
    )
    winning_tags_df.insert(0, "date", run_date)
    # Keep top 13 tags per niche
    winning_tags_df = winning_tags_df.groupby("niche", as_index=False).head(13)

    return scorecard_df, winning_tags_df
