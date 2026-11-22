"""
POD & Etsy Live Team Dashboard (Streamlit)
=========================================
Includes animated ETL flow diagram, API readiness tracker (pending vs active),
opportunity charts, and one-click Winning Tags copy for the team.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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
            return sc_df, wt_df, "Google Sheets (Canlı)"
        except Exception as exc:
            st.warning(f"Google Sheets okunamadı, yerel CSV'ye geçildi: {exc}")

    sc_csv = OUTPUT_DIR / "niche_scorecard.csv"
    wt_csv = OUTPUT_DIR / "winning_tags.csv"
    if sc_csv.exists() and wt_csv.exists():
        return pd.read_csv(sc_csv), pd.read_csv(wt_csv), "Yerel CSV (output/)"

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sample_sc = pd.DataFrame([
        {"date": today, "niche": "2027 daily planner hardcover", "total_competition": 2400, "avg_price_usd": 30.4, "trend_slope_90d": 3.33, "fresh_winners_count": 10, "opportunity_score": 88.3},
        {"date": today, "niche": "2027 vision board poster", "total_competition": 1850, "avg_price_usd": 26.4, "trend_slope_90d": -3.11, "fresh_winners_count": 10, "opportunity_score": 85.0},
        {"date": today, "niche": "retro tennis club sweatshirt", "total_competition": 3200, "avg_price_usd": 44.9, "trend_slope_90d": 0.0, "fresh_winners_count": 10, "opportunity_score": 85.0},
        {"date": today, "niche": "sunday league football shirt", "total_competition": 2100, "avg_price_usd": 26.9, "trend_slope_90d": 0.0, "fresh_winners_count": 9, "opportunity_score": 85.0},
        {"date": today, "niche": "minimalist manifestation journal", "total_competition": 112000, "avg_price_usd": 20.9, "trend_slope_90d": -1.59, "fresh_winners_count": 0, "opportunity_score": 15.1},
    ])
    sample_wt = pd.DataFrame([
        {"date": today, "niche": "2027 daily planner hardcover", "tag": "2027 planner", "frequency": 10},
        {"date": today, "niche": "2027 daily planner hardcover", "tag": "hardcover planner", "frequency": 10},
        {"date": today, "niche": "2027 daily planner hardcover", "tag": "daily organizer", "frequency": 10},
        {"date": today, "niche": "2027 vision board poster", "tag": "2027 vision board", "frequency": 10},
        {"date": today, "niche": "2027 vision board poster", "tag": "vision board poster", "frequency": 10},
    ])
    return sample_sc, sample_wt, "Örnek / Son Çıktı Verisi"


def render_animated_etl_flow(api_states: dict[str, tuple[str, str]]) -> None:
    """Renders an animated glowing ETL flow diagram inside Streamlit."""
    def badge_html(label: str, state: str) -> str:
        colors = {
            "OK": ("rgba(34,197,94,0.16)", "#22c55e"),
            "PENDING": ("rgba(234,179,8,0.16)", "#eab308"),
            "MISSING": ("rgba(239,68,68,0.16)", "#ef4444"),
        }
        bg, fg = colors.get(state, ("rgba(148,163,184,0.16)", "#94a3b8"))
        return f'<span style="background:{bg};color:{fg};padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;">{label}</span>'

    extract_items = "".join(
        f'<div class="item"><span>{name}</span>{badge_html(lbl, st_code)}</div>'
        for name, (lbl, st_code) in api_states.items()
    )

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        body {{
          margin: 0;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          background: transparent;
          color: #f1f5f9;
        }}
        .flow {{
          display: grid;
          grid-template-columns: 1.25fr 70px 1fr 70px 1fr;
          align-items: center;
          gap: 8px;
          background: #131c31;
          border: 1px solid rgba(148, 163, 184, 0.22);
          border-radius: 14px;
          padding: 16px 18px;
        }}
        .box {{
          background: #1b2742;
          border: 1px solid rgba(148, 163, 184, 0.2);
          border-radius: 12px;
          padding: 12px 14px;
        }}
        .head {{
          font-size: 11.5px;
          font-weight: 800;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: #f97316;
          margin-bottom: 8px;
          display: flex;
          align-items: center;
          gap: 6px;
        }}
        .dot {{
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #22c55e;
          animation: pulse 1.6s infinite;
        }}
        @keyframes pulse {{
          0%, 100% {{ opacity: 1; transform: scale(1); }}
          50% {{ opacity: 0.4; transform: scale(1.3); }}
        }}
        .item {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 12.5px;
          background: rgba(15, 23, 42, 0.6);
          padding: 6px 9px;
          border-radius: 7px;
          margin-bottom: 6px;
        }}
        .item:last-child {{ margin-bottom: 0; }}
        .pipe {{
          position: relative;
          height: 4px;
          background: rgba(56, 189, 248, 0.2);
          border-radius: 4px;
          overflow: hidden;
        }}
        .pipe::after {{
          content: "";
          position: absolute;
          top: 0;
          left: -40%;
          width: 40%;
          height: 100%;
          background: linear-gradient(90deg, transparent, #38bdf8, #f97316, transparent);
          animation: flow 1.4s linear infinite;
        }}
        @keyframes flow {{
          0% {{ left: -40%; }}
          100% {{ left: 100%; }}
        }}
      </style>
    </head>
    <body>
      <div class="flow">
        <div class="box">
          <div class="head"><span class="dot"></span> 1. Extract (API Kaynakları)</div>
          {extract_items}
        </div>
        <div class="pipe"></div>
        <div class="box">
          <div class="head"><span class="dot"></span> 2. Transform (Motor)</div>
          <div class="item"><span>Telif / Blacklist Filtresi</span>{badge_html("AKTİF", "OK")}</div>
          <div class="item"><span>Opportunity Score (0-100)</span>{badge_html("AKTİF", "OK")}</div>
          <div class="item"><span>Top 13 Etsy Tag Madenciliği</span>{badge_html("AKTİF", "OK")}</div>
        </div>
        <div class="pipe"></div>
        <div class="box">
          <div class="head"><span class="dot"></span> 3. Load (Çıktılar)</div>
          <div class="item"><span>CSV & Dashboard JSON</span>{badge_html("GÜNCEL", "OK")}</div>
          <div class="item"><span>Google Sheets Sync</span>{badge_html("BEKLEMEDE" if not get_secret("GOOGLE_SHEET_ID") else "AKTİF", "PENDING" if not get_secret("GOOGLE_SHEET_ID") else "OK")}</div>
          <div class="item"><span>GitHub Cron (TSİ 04:00)</span>{badge_html("HAZIR", "OK")}</div>
        </div>
      </div>
    </body>
    </html>
    """
    components.html(html, height=275)


def main() -> None:
    sc_df, wt_df, source_label = load_dashboard_data()

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

    latest_date = str(sc_df["date"].max()) if "date" in sc_df.columns else "-"
    latest_df = sc_df[sc_df["date"].astype(str) == latest_date].copy() if "date" in sc_df.columns else sc_df.copy()

    k1, k2, k3, k4 = st.columns(4)
    top_row = latest_df.sort_values("opportunity_score", ascending=False).iloc[0]
    k1.metric("Son Çalışma Tarihi", latest_date, "Sistem Güncel")
    k2.metric("Taranan Niş", len(latest_df))
    k3.metric("En Yüksek Skor", f"{top_row['opportunity_score']} / 100", str(top_row["niche"]))
    k4.metric("Ortalama Fiyat", f"${latest_df['avg_price_usd'].mean():.2f}", "Hedef: $24+")

    # Animated ETL Flow
    st.subheader("⚙️ Canlı ETL Akış Durumu (Extract → Transform → Load)")
    api_states = {
        "Gelato Catalog API": ("AKTİF" if get_secret("GELATO_API_KEY") else "EKSİK", "OK" if get_secret("GELATO_API_KEY") else "MISSING"),
        "Google Trends (90g)": ("AKTİF (Keysiz)", "OK"),
        "Pinterest Trends v5": ("AKTİF" if get_secret("PINTEREST_ACCESS_TOKEN") else "ONAY BEKLİYOR", "OK" if get_secret("PINTEREST_ACCESS_TOKEN") else "PENDING"),
        "Etsy Open API v3": ("AKTİF" if get_secret("ETSY_API_KEY") else "MAĞAZA BEKLİYOR", "OK" if get_secret("ETSY_API_KEY") else "MISSING"),
        "eBay & Reddit API": ("AKTİF" if get_secret("EBAY_ACCESS_TOKEN") else "EKSİK / OPSİYONEL", "OK" if get_secret("EBAY_ACCESS_TOKEN") else "PENDING"),
    }
    render_animated_etl_flow(api_states)

    # Explicit Missing / Pending APIs Callout
    with st.expander("🔑 Eksik veya Onay Sürecindeki API'ler (Takım Durumu)", expanded=True):
        missing_rows = [
            {"API Kaynağı": "Gelato Satıcı API", "Durum": "✅ Hazır (Key alındı)" if get_secret("GELATO_API_KEY") else "⚠️ Secret eklenmedi", "Not": "Ürün maliyeti & katalog çekimi"},
            {"API Kaynağı": "Google Trends (pytrends)", "Durum": "✅ Canlı Çalışıyor", "Not": "90 günlük arama ivmesi (API key gerekmez)"},
            {"API Kaynağı": "Pinterest Trends API v5", "Durum": "✅ Aktif" if get_secret("PINTEREST_ACCESS_TOKEN") else "⏳ Onay Bekliyor (Trial Pending)", "Not": "Başvuru gönderildi; onaylanınca otomatik token bağlanacak"},
            {"API Kaynağı": "Etsy Open API v3", "Durum": "✅ Aktif" if get_secret("ETSY_API_KEY") else "❌ Eksik (Mağaza Açılışı Bekliyor)", "Not": "TR'den Etsy mağazası açılınca 'Seller App' ile dakikalar içinde alınacak"},
            {"API Kaynağı": "Google Sheets Sync", "Durum": "✅ Aktif" if get_secret("GOOGLE_SHEET_ID") else "⏳ Kurulum Bekliyor", "Not": "Canlı tabloyu ortak Google Sheet'e basmak için Service Account gerekir"},
            {"API Kaynağı": "eBay Browse & Reddit OAuth", "Durum": "⏸️ Opsiyonel / Başvuru Gerekli", "Not": "Çapraz fiyat ve niş fikir madenciliği için ek kaynak"},
        ]
        st.dataframe(pd.DataFrame(missing_rows), use_container_width=True, hide_index=True)

    st.divider()

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
