"""
Load Layer
==========
- Always writes local CSV backups to output/
- Pushes Niche_Scorecard and Winning_Tags to Google Sheets via gspread if credentials are configured
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path

import pandas as pd


def _get_gspread_client():
    import gspread
    from google.oauth2.service_account import Credentials

    creds_raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not creds_raw:
        return None

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    if creds_raw.startswith("{"):
        info = json.loads(creds_raw)
        creds = Credentials.from_service_account_info(info, scopes=scopes)
    else:
        creds_path = Path(creds_raw)
        if not creds_path.exists():
            return None
        creds = Credentials.from_service_account_file(str(creds_path), scopes=scopes)

    return gspread.authorize(creds)


def _upsert_worksheet(spreadsheet, title: str, df: pd.DataFrame, append: bool = True) -> None:
    try:
        ws = spreadsheet.worksheet(title)
    except Exception:
        ws = spreadsheet.add_worksheet(title=title, rows=1000, cols=max(10, len(df.columns)))
        ws.append_row(df.columns.tolist(), value_input_option="USER_ENTERED")

    rows = df.values.tolist()
    if not rows:
        return

    if append:
        existing = ws.get_all_values()
        if not existing:
            ws.append_row(df.columns.tolist(), value_input_option="USER_ENTERED")
        ws.append_rows(rows, value_input_option="USER_ENTERED")
    else:
        ws.clear()
        ws.update([df.columns.tolist()] + rows, value_input_option="USER_ENTERED")


def load_outputs(
    scorecard_df: pd.DataFrame,
    winning_tags_df: pd.DataFrame,
    output_dir: Path,
    pipeline_meta: dict | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    scorecard_csv = output_dir / "niche_scorecard.csv"
    tags_csv = output_dir / "winning_tags.csv"
    dashboard_js = output_dir / "dashboard_data.js"

    scorecard_df.to_csv(scorecard_csv, index=False, encoding="utf-8-sig")
    winning_tags_df.to_csv(tags_csv, index=False, encoding="utf-8-sig")
    print(f"[Load] Saved local CSVs: {scorecard_csv} & {tags_csv}")

    payload = {
        "last_run_at": datetime.now(timezone.utc).isoformat(),
        "meta": pipeline_meta or {
            "status": "OK",
            "mode": "LIVE",
            "sources": {
                "etsy": "OK" if os.getenv("ETSY_API_KEY") else "MOCK",
                "gelato": "OK" if os.getenv("GELATO_API_KEY") else "SKIPPED",
                "google_trends": "OK",
                "pinterest": "OK" if os.getenv("PINTEREST_ACCESS_TOKEN") else "SKIPPED",
                "ebay": "OK" if os.getenv("EBAY_ACCESS_TOKEN") else "SKIPPED",
                "reddit": "OK",
            },
        },
        "scorecard": scorecard_df.to_dict(orient="records"),
        "winning_tags": winning_tags_df.to_dict(orient="records"),
    }
    dashboard_js.write_text(
        "window.DASHBOARD_DATA = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    print(f"[Load] Updated dashboard data: {dashboard_js}")

    sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
    client = _get_gspread_client()
    if client and sheet_id:
        spreadsheet = client.open_by_key(sheet_id)
        _upsert_worksheet(spreadsheet, "Niche_Scorecard", scorecard_df, append=True)
        _upsert_worksheet(spreadsheet, "Winning_Tags", winning_tags_df, append=False)
        print(f"[Load] Synced to Google Sheets (ID: {sheet_id})")
    else:
        print("[Load] Google Sheets credentials not configured -> skipped Sheets sync (local CSVs saved).")
