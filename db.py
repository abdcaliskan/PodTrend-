"""
SQLite Data Warehouse for POD Keyword & Trend Snapshots
"""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "pod_warehouse.db"


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS keyword_snapshots (
                snapshot_date TEXT NOT NULL,
                keyword TEXT NOT NULL,
                status TEXT NOT NULL,
                opportunity_score REAL NOT NULL,
                recommended_product TEXT NOT NULL,
                avg_price_usd REAL NOT NULL,
                est_net_profit_usd REAL NOT NULL,
                avg_monthly_sales REAL NOT NULL,
                avg_reviews REAL NOT NULL,
                total_results INTEGER NOT NULL,
                new_shop_signal TEXT NOT NULL,
                top_13_etsy_tags TEXT NOT NULL,
                PRIMARY KEY (snapshot_date, keyword)
            )
            """
        )
        conn.commit()


def upsert_snapshots(rows: list[dict], snapshot_date: str, db_path: Path = DEFAULT_DB_PATH) -> None:
    init_db(db_path)
    with get_connection(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO keyword_snapshots (
                snapshot_date, keyword, status, opportunity_score,
                recommended_product, avg_price_usd, est_net_profit_usd,
                avg_monthly_sales, avg_reviews, total_results,
                new_shop_signal, top_13_etsy_tags
            ) VALUES (
                :snapshot_date, :keyword, :status, :opportunity_score,
                :recommended_product, :avg_price_usd, :est_net_profit_usd,
                :avg_monthly_sales, :avg_reviews, :total_results,
                :new_shop_signal, :top_13_etsy_tags
            )
            ON CONFLICT(snapshot_date, keyword) DO UPDATE SET
                status = excluded.status,
                opportunity_score = excluded.opportunity_score,
                recommended_product = excluded.recommended_product,
                avg_price_usd = excluded.avg_price_usd,
                est_net_profit_usd = excluded.est_net_profit_usd,
                avg_monthly_sales = excluded.avg_monthly_sales,
                avg_reviews = excluded.avg_reviews,
                total_results = excluded.total_results,
                new_shop_signal = excluded.new_shop_signal,
                top_13_etsy_tags = excluded.top_13_etsy_tags
            """,
            [{**r, "snapshot_date": snapshot_date} for r in rows],
        )
        conn.commit()


def get_latest_two_dates(db_path: Path = DEFAULT_DB_PATH) -> list[str]:
    init_db(db_path)
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "SELECT DISTINCT snapshot_date FROM keyword_snapshots ORDER BY snapshot_date DESC LIMIT 2"
        )
        return [row["snapshot_date"] for row in cur.fetchall()]


def get_snapshot_by_date(snapshot_date: str, db_path: Path = DEFAULT_DB_PATH) -> dict[str, dict]:
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "SELECT * FROM keyword_snapshots WHERE snapshot_date = ?",
            (snapshot_date,),
        )
        return {row["keyword"]: dict(row) for row in cur.fetchall()}
