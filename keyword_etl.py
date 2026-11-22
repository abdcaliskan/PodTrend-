"""
POD & Etsy Keyword Research ETL Pipeline
========================================
Extract   -> Reads EverBee / eRank style CSV exports
Transform -> Filters trademark risks, calculates net profit & opportunity score, mines top 13 Etsy tags
Load      -> Outputs clean design_briefs.csv and rejected_trademarks.csv for the team
"""

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from db import DEFAULT_DB_PATH, upsert_snapshots

ETSY_FEE_RATE = 0.12  # ~12% (transaction + payment + listing estimate)
ETSY_MAX_TAG_LEN = 20


def load_blacklist(path: Path) -> list[str]:
    if not path.exists():
        return []
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip().lower()
        if cleaned and not cleaned.startswith("#"):
            terms.append(cleaned)
    return terms


def load_costs(path: Path) -> dict[str, float]:
    if not path.exists():
        return {"default": 14.0}
    return json.loads(path.read_text(encoding="utf-8"))


def find_trademark_hit(text: str, blacklist: list[str]) -> str | None:
    lowered = text.lower()
    for term in blacklist:
        if term in lowered:
            return term
    return None


def safe_float(val: str, default: float = 0.0) -> float:
    try:
        return float(str(val).replace("$", "").replace("€", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return default


def safe_int(val: str, default: int = 0) -> int:
    try:
        return int(float(str(val).replace(",", "").strip()))
    except (ValueError, TypeError):
        return default


def extract_rows(csv_path: Path) -> list[dict]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [row for row in reader if any(v.strip() for v in row.values() if v)]


def compute_opportunity_score(
    avg_sales: float,
    avg_reviews: float,
    total_results: int,
    avg_profit: float,
    new_shop_signal: bool,
) -> float:
    """Computes a 0-10 score balancing demand, competition, margin, and new-shop viability."""
    if avg_profit <= 2.0:
        return 0.0

    demand_score = min(avg_sales / 15.0, 4.0)  # up to 4 pts
    margin_score = min(avg_profit / 4.0, 2.5)  # up to 2.5 pts

    # Lower competition & lower reviews = higher score
    comp_penalty = math.log10(max(total_results, 10))  # ~3.0 for 1k, ~5.0 for 100k
    competition_score = max(0.0, 2.5 - max(0.0, comp_penalty - 2.5))  # up to 2.5 pts
    if avg_reviews > 300:
        competition_score *= 0.5

    viability_bonus = 1.0 if new_shop_signal else 0.0  # up to 1 pt
    total = demand_score + margin_score + competition_score + viability_bonus
    return round(min(total, 10.0), 2)


def run_etl(
    input_path: Path,
    output_dir: Path,
    blacklist_path: Path,
    costs_path: Path,
    snapshot_date: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    blacklist = load_blacklist(blacklist_path)
    costs = load_costs(costs_path)
    raw_rows = extract_rows(input_path)

    grouped: dict[str, list[dict]] = defaultdict(list)
    rejected: list[dict] = []

    # TRANSFORM: Filter & enrich per-listing metrics
    for row in raw_rows:
        keyword = (row.get("keyword") or "").strip().lower()
        title = (row.get("title") or "").strip()
        tags_raw = (row.get("tags") or "").strip()
        combined_text = f"{keyword} {title} {tags_raw}"

        hit = find_trademark_hit(combined_text, blacklist)
        if hit:
            rejected.append({
                "keyword": keyword,
                "title": title,
                "matched_trademark": hit,
            })
            continue

        price = safe_float(row.get("price_usd"))
        product_type = (row.get("product_type") or "default").strip().lower()
        base_cost = costs.get(product_type, costs.get("default", 14.0))
        etsy_fee = price * ETSY_FEE_RATE
        net_profit = round(price - base_cost - etsy_fee, 2)

        grouped[keyword].append({
            "price": price,
            "sales": safe_int(row.get("est_monthly_sales")),
            "reviews": safe_int(row.get("reviews")),
            "age_months": safe_int(row.get("listing_age_months"), 99),
            "favorites": safe_int(row.get("favorites")),
            "total_results": safe_int(row.get("total_results"), 10000),
            "product_type": product_type,
            "net_profit": net_profit,
            "tags": [t.strip().lower() for t in tags_raw.split(",") if t.strip()],
        })

    # TRANSFORM: Aggregate by keyword & mine top 13 Etsy tags
    briefs: list[dict] = []
    for kw, items in grouped.items():
        n = len(items)
        avg_price = round(sum(i["price"] for i in items) / n, 2)
        avg_sales = round(sum(i["sales"] for i in items) / n, 1)
        avg_reviews = round(sum(i["reviews"] for i in items) / n, 1)
        avg_profit = round(sum(i["net_profit"] for i in items) / n, 2)
        total_results = max(i["total_results"] for i in items)
        main_product = Counter(i["product_type"] for i in items).most_common(1)[0][0]

        new_shop_signal = any(
            (i["reviews"] < 100 or i["age_months"] <= 6) and i["sales"] >= 10
            for i in items
        )

        score = compute_opportunity_score(
            avg_sales=avg_sales,
            avg_reviews=avg_reviews,
            total_results=total_results,
            avg_profit=avg_profit,
            new_shop_signal=new_shop_signal,
        )

        # Mine top 13 valid Etsy tags (<= 20 chars)
        tag_counter: Counter[str] = Counter()
        for i in items:
            for t in i["tags"]:
                if len(t) <= ETSY_MAX_TAG_LEN:
                    tag_counter[t] += 1
        top_13_tags = [tag for tag, _ in tag_counter.most_common(13)]

        status = "PRIORITY" if score >= 7.0 else ("TEST" if score >= 4.5 else "SKIP")

        briefs.append({
            "status": status,
            "opportunity_score": score,
            "keyword": kw,
            "recommended_product": main_product,
            "avg_price_usd": avg_price,
            "est_net_profit_usd": avg_profit,
            "avg_monthly_sales": avg_sales,
            "avg_reviews": avg_reviews,
            "total_results": total_results,
            "new_shop_signal": "YES" if new_shop_signal else "NO",
            "top_13_etsy_tags": ", ".join(top_13_tags),
        })

    briefs.sort(key=lambda x: x["opportunity_score"], reverse=True)

    # LOAD: Write outputs & persist historical snapshot to SQLite
    if briefs:
        upsert_snapshots(briefs, snapshot_date=snapshot_date, db_path=db_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    briefs_path = output_dir / "design_briefs.csv"
    rejected_path = output_dir / "rejected_trademarks.csv"

    if briefs:
        with briefs_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(briefs[0].keys()))
            writer.writeheader()
            writer.writerows(briefs)

    with rejected_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["keyword", "title", "matched_trademark"])
        writer.writeheader()
        writer.writerows(rejected)

    # Terminal summary
    print(f"\n[ETL Complete] Processed {len(raw_rows)} listings -> {len(briefs)} clean keywords, {len(rejected)} trademark-rejected.")
    print(f"Output saved to: {briefs_path}\n")
    print(f"{'STATUS':<9} {'SCORE':<6} {'KEYWORD':<32} {'PRODUCT':<9} {'PROFIT($)':<10} {'NEW_SHOP'}")
    print("-" * 80)
    for b in briefs:
        print(
            f"{b['status']:<9} {b['opportunity_score']:<6} {b['keyword']:<32} "
            f"{b['recommended_product']:<9} {b['est_net_profit_usd']:<10} {b['new_shop_signal']}"
        )


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="POD & Etsy Keyword Research ETL")
    parser.add_argument("--input", type=Path, default=base_dir / "sample_input.csv", help="Path to input CSV")
    parser.add_argument("--output-dir", type=Path, default=base_dir / "output", help="Output directory")
    parser.add_argument("--blacklist", type=Path, default=base_dir / "trademark_blacklist.txt", help="Trademark blacklist")
    parser.add_argument("--costs", type=Path, default=base_dir / "gelato_costs.json", help="Product cost mapping")
    parser.add_argument("--date", type=str, default=date.today().isoformat(), help="Snapshot date (YYYY-MM-DD)")
    args = parser.parse_args()

    run_etl(args.input, args.output_dir, args.blacklist, args.costs, snapshot_date=args.date)


if __name__ == "__main__":
    main()
