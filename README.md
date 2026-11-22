# PodTrend Analytics — POD & Etsy Keyword ETL

Automated daily/weekly ETL pipeline (`Extract → Transform → Load`) for Print-on-Demand & Etsy keyword research, trend tracking, and team collaboration.

## Architecture
- `extract.py` — Etsy Open API v3, Gelato Catalog API, Google Trends (`pytrends`), Pinterest Trends v5, eBay Browse API, Reddit
- `transform.py` — Trademark blacklist filtering, Opportunity Score (0–100), Top 13 Etsy tag mining
- `load.py` — Google Sheets sync (`Niche_Scorecard`, `Winning_Tags`), local CSV backups, and `dashboard_data.js`
- `app.py` — Streamlit team dashboard
- `.github/workflows/etl.yml` — Automated daily run (TSİ 04:00)

## Quick Start
```bash
pip install -r requirements.txt
cp .env.example .env
python main.py --mock
streamlit run app.py
```
