"""
Main ETL Orchestrator
=====================
Runs Extract -> Transform -> Load for the niches defined in niches.txt.
"""

import argparse
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

from extract import extract_all
from load import load_outputs
from transform import transform_data


def load_niches(path: Path) -> list[str]:
    if not path.exists():
        return ["2027 vision board poster", "2027 daily planner hardcover"]
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    load_dotenv(base_dir / ".env")

    parser = argparse.ArgumentParser(description="Etsy + Google Trends -> Google Sheets ETL")
    parser.add_argument("--niches-file", type=Path, default=base_dir / "niches.txt")
    parser.add_argument("--blacklist", type=Path, default=base_dir / "trademark_blacklist.txt")
    parser.add_argument("--output-dir", type=Path, default=base_dir / "output")
    parser.add_argument("--mock", action="store_true", help="Run with mock data (no API keys needed)")
    args = parser.parse_args()

    niches = load_niches(args.niches_file)
    print(f"[Main] Starting ETL for {len(niches)} niches...")

    raw_listings, trend_slopes, meta = extract_all(niches, use_mock=args.mock)
    scorecard_df, winning_tags_df = transform_data(
        raw_listings, trend_slopes, blacklist_path=args.blacklist
    )

    if scorecard_df.empty:
        print("[Main] No valid data after filtering.")
        return

    print("\n=== NICHE SCORECARD (0-100) ===")
    print(scorecard_df.to_string(index=False))
    load_outputs(scorecard_df, winning_tags_df, output_dir=args.output_dir, pipeline_meta=meta)


if __name__ == "__main__":
    main()
