"""
Main ETL Orchestrator (100% Dynamic Live Discovery)
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


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    load_dotenv(base_dir / ".env")

    parser = argparse.ArgumentParser(description="100% Dynamic POD Keyword ETL")
    parser.add_argument("--blacklist", type=Path, default=base_dir / "trademark_blacklist.txt")
    parser.add_argument("--output-dir", type=Path, default=base_dir / "output")
    args = parser.parse_args()

    print("[Main] Starting 100% dynamic live extraction...")
    extracted = extract_all()
    scorecard_df, winning_tags_df = transform_data(extracted, blacklist_path=args.blacklist)

    if scorecard_df.empty:
        print("[Main] No live trend keywords returned (Google Trends may be rate-limited).")
        return

    print(f"\n=== DISCOVERED LIVE TRENDS ({len(scorecard_df)} keywords) ===")
    print(scorecard_df.head(15).to_string(index=False))

    meta = extracted["meta"]
    meta["reddit_posts"] = extracted.get("reddit_posts", [])
    load_outputs(scorecard_df, winning_tags_df, output_dir=args.output_dir, pipeline_meta=meta)


if __name__ == "__main__":
    main()
