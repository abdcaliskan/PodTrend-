"""
POD & Etsy Live Team Dashboard (Streamlit)
=========================================
Reads from Google Sheets (if configured via .env / st.secrets) or local output/*.csv backups.
Deployable for free on Streamlit Community Cloud.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="POD & Etsy — Canlı Ekip Dashboard",
    page_icon="📊",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"


def get_secret(key: str) -> str:
    if key in os.environ and os.environ[key].strip():
        return os.environ[key].strip()
    try:
        if key in st.secrets:
            val = st.secrets[key]
            return json.dumps(dict(val)) if hasattr(val, "items") else str(val)
    except Exception:
        pass
    return ""


@st.cache_data(ttl=300)
def load_dashboard_data() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Loads Niche_Scorecard and Winning_Tags from Google Sheets, local CSVs, or fallback sample."""
    sheet_id = get_secret("GOOGLE_SHEET_ID")
    creds_raw = get_secret("GOOGLE_SERVICE_ACCOUNT_JSON")

    if sheet_id and creds_raw:
        try:
            import gspread
            from google.oauth2.service_account import Credentials

            scopes = [
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly",
            ]
            if creds_raw.startswith("{"):
                creds = Credentials.from_service_account_info(json.loads(creds_raw), scopes=scopes)
            else:
                creds = Credentials.from_service_account_file(creds_raw, scopes=scopes)

            client = gspread.authorize(creds)
            ss = client.open_by_key(sheet_id)
            sc_df = pd.DataFrame(ss.worksheet("Niche_Scorecard").get_all_records())
            wt_df = pd.DataFrame(ss.worksheet("Winning_Tags").get_all_records())
            return sc_df, wt_df, "Google Sheets (Live)"
        except Exception as exc:
            st.warning(f"Google Sheets okunamadı, yerel CSV'ye geçildi: {exc}")

    sc_csv = OUTPUT_DIR / "niche_scorecard.csv"
    wt_csv = OUTPUT_DIR / "winning_tags.csv"
    if sc_csv.exists() and wt_csv.exists():
        return pd.read_csv(sc_csv), pd.read_csv(wt_csv), "Yerel CSV (output/)"

    # Fallback sample so first deploy works immediately
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sample_sc = pd.DataFrame([
        {"date": today, "niche": "2027 vision board poster", "total_competition": 1850, "avg_price_usd": 26.5, "trend_slope_90d": 12.5, "fresh_winners_count": 10, "opportunity_score": 97.5},
        {"date": today, "niche": "2027 daily planner hardcover", "total_competition": 2400, "avg_price_usd": 30.5, "trend_slope_90d": 12.5, "fresh_winners_count": 10, "opportunity_score": 97.5},
        {"date": today, "niche": "retro tennis club sweatshirt", "total_competition": 3200, "avg_price_usd": 45.0, "trend_slope_90d": 12.5, "fresh_winners_count": 10, "opportunity_score": 97.5},
        {"date": today, "niche": "sunday league football shirt", "total_competition": 2100, "avg_price_usd": 27.0, "trend_slope_90d": 12.5, "fresh_winners_count": 10, "opportunity_score": 97.5},
    ])
    sample_wt = pd.DataFrame([
        {"date": today, "niche": "2027 vision board poster", "tag": "2027 vision board", "frequency": 10},
        {"date": today, "niche": "2027 vision board poster", "tag": "vision board poster", "frequency": 10},
        {"date": today, "niche": "2027 vision board poster", "tag": "manifestation art", "frequency": 10},
        {"date": today, "niche": "2027 daily planner hardcover", "tag": "2027 planner", "frequency": 10},
        {"date": today, "niche": "2027 daily planner hardcover", "tag": "hardcover planner", "frequency": 10},
    ])
    return sample_sc, sample_wt, "Örnek Veri (Henüz ETL çalıştırılmadı)"


def main() -> None:
    sc_df, wt_df, source_label = load_dashboard_data()

    # Header & Refresh
    col_title, col_btn = st.columns([4, 1])
    with col_title:
        st.title("📊 POD & Etsy — Canlı Ekip Dashboard")
        st.caption(f"Veri Kaynağı: **{source_label}** • Tüm ekip (Sen, Reyna, TR Mağaza) için ortak takip ekranı")
    with col_btn:
        if st.button("🔄 Veriyi Yenile", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    if sc_df.empty:
        st.info("Henüz niş verisi bulunmuyor.")
        return

    # Latest snapshot date & freshness
    latest_date = str(sc_df["date"].max()) if "date" in sc_df.columns else "-"
    latest_df = sc_df[sc_df["date"].astype(str) == latest_date].copy() if "date" in sc_df.columns else sc_df.copy()

    # KPI Row
    k1, k2, k3, k4 = st.columns(4)
    top_row = latest_df.sort_values("opportunity_score", ascending=False).iloc[0]
    k1.metric("Son Çalışma Tarihi", latest_date, "Sistem Güncel")
    k2.metric("Taranan Niş", len(latest_df))
    k3.metric("En Yüksek Skor", f"{top_row['opportunity_score']} / 100", str(top_row["niche"]))
    k4.metric("Ortalama Fiyat", f"${latest_df['avg_price_usd'].mean():.2f}", "Hedef: $24+")

    st.divider()

    # Pipeline Status Flow
    st.subheader("⚙️ ETL Akış Durumu (Extract → Transform → Load)")
    f1, f2, f3 = st.columns(3)
    with f1:
        st.markdown("**1. Extract (Veri Kaynakları)**")
        st.success(f"Etsy API: {'Aktif' if get_secret('ETSY_API_KEY') else 'Mock / Beklemede'}")
        st.info(f"Gelato API: {'Aktif' if get_secret('GELATO_API_KEY') else 'Opsiyonel'}")
        st.info(f"Pinterest / eBay: {'Aktif' if get_secret('PINTEREST_ACCESS_TOKEN') or get_secret('EBAY_ACCESS_TOKEN') else 'Opsiyonel'}")
    with f2:
        st.markdown("**2. Transform (Analiz & Skor)**")
        st.success("Telif / Blacklist Filtresi: Aktif")
        st.success("Opportunity Score (0-100): Aktif")
        st.success("Top 13 Etsy Tag Madenciliği: Aktif")
    with f3:
        st.markdown("**3. Load (Hedef Katman)**")
        st.success(f"Aktif Kaynak: {source_label}")
        st.info("GitHub Actions Cron: Her gece TSİ 04:00")

    st.divider()

    # Sidebar / Inline Filters
    st.subheader("📈 Niş Skorları & Reyna İçin Hazır Etiketler")
    c_filter1, c_filter2 = st.columns([2, 1])
    with c_filter1:
        search_q = st.text_input("Niş Ara", placeholder="Örn: planner, vision, tennis...")
    with c_filter2:
        min_score = st.slider("Minimum Fırsat Skoru", 0, 100, 0)

    filtered = latest_df[
        (latest_df["opportunity_score"] >= min_score)
        & (latest_df["niche"].astype(str).str.lower().str.contains(search_q.lower().strip()))
    ].sort_values("opportunity_score", ascending=False)

    left_col, right_col = st.columns([1.2, 1])
    with left_col:
        st.markdown("**Fırsat Skoru Karşılaştırması**")
        if not filtered.empty:
            chart_df = filtered.set_index("niche")[["opportunity_score"]]
            st.bar_chart(chart_df)
        st.dataframe(filtered, use_container_width=True, hide_index=True)

    with right_col:
        st.markdown("**🏷️ Seçili Niş İçin En İyi Etiketler (Winning Tags)**")
        niche_options = filtered["niche"].tolist() if not filtered.empty else latest_df["niche"].tolist()
        selected_niche = st.selectbox("Niş Seç", niche_options)
        if selected_niche and not wt_df.empty:
            niche_tags = wt_df[wt_df["niche"] == selected_niche].sort_values("frequency", ascending=False)
            tags_list = niche_tags["tag"].astype(str).tolist()[:13]
            st.write("Etsy'ye doğrudan yapıştırmak için (sağ üstten kopyala):")
            st.code(", ".join(tags_list), language=None)
            st.dataframe(niche_tags[["tag", "frequency"]].head(13), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
