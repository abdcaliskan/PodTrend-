"""
POD & Etsy Live Team Dashboard (Streamlit)
=========================================
Unified dark-slate design language across:
- Animated ETL flow diagram
- API readiness tracker (pending vs active)
- Custom horizontal opportunity bar chart & styled scorecard table
- One-click Winning Tags copy for Reyna & Etsy
"""

import json
import os
from datetime import datetime, timezone
from html import escape
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


from extract import extract_all
from transform import transform_data


@st.cache_data(ttl=3600)
def load_dashboard_data(force_live: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Loads Niche_Scorecard and Winning_Tags from Google Sheets, local CSVs, or live extraction."""
    sheet_id = get_secret("GOOGLE_SHEET_ID")
    creds_raw = get_secret("GOOGLE_SERVICE_ACCOUNT_JSON")

    if sheet_id and creds_raw and not force_live:
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
    if sc_csv.exists() and not force_live:
        try:
            sc_df = pd.read_csv(sc_csv)
        except pd.errors.EmptyDataError:
            sc_df = pd.DataFrame()
        try:
            wt_df = pd.read_csv(wt_csv) if wt_csv.exists() else pd.DataFrame()
        except pd.errors.EmptyDataError:
            wt_df = pd.DataFrame()
        if not sc_df.empty:
            return sc_df, wt_df, "Canlı ETL Çıktısı (output/niche_scorecard.csv)"

    extracted = extract_all()
    sc_df, wt_df = transform_data(extracted, blacklist_path=BASE_DIR / "trademark_blacklist.txt")
    return sc_df, wt_df, "Canlı API Taraması (Google Trends + Gelato)"


BASE_CSS = """
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif;
  background: transparent;
  color: #f1f5f9;
}
.card {
  background: #131c31;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 14px;
  padding: 16px 20px;
}
.badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}
.badge.ok { background: rgba(34,197,94,0.16); color: #22c55e; }
.badge.pending { background: rgba(234,179,8,0.16); color: #eab308; }
.badge.missing { background: rgba(239,68,68,0.16); color: #ef4444; }
.badge.mid { background: rgba(249,115,22,0.16); color: #f97316; }
"""


def render_animated_etl_flow(api_states: dict[str, tuple[str, str]]) -> None:
    def badge(label: str, state: str) -> str:
        cls = {"OK": "ok", "PENDING": "pending", "MISSING": "missing"}.get(state, "pending")
        return f'<span class="badge {cls}">{escape(label)}</span>'

    extract_items = "".join(
        f'<div class="item"><span>{escape(name)}</span>{badge(lbl, st_code)}</div>'
        for name, (lbl, st_code) in api_states.items()
    )

    html = f"""<!DOCTYPE html><html><head><style>
    {BASE_CSS}
    .flow {{
      display: grid;
      grid-template-columns: 1.25fr 70px 1fr 70px 1fr;
      align-items: center;
      gap: 8px;
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
    @keyframes flow {{ 0% {{ left: -40%; }} 100% {{ left: 100%; }} }}
    </style></head><body>
      <div class="card flow">
        <div class="box">
          <div class="head"><span class="dot"></span> 1. Extract (API Kaynakları)</div>
          {extract_items}
        </div>
        <div class="pipe"></div>
        <div class="box">
          <div class="head"><span class="dot"></span> 2. Transform (Motor)</div>
          <div class="item"><span>Telif / Blacklist Filtresi</span>{badge("AKTİF", "OK")}</div>
          <div class="item"><span>Opportunity Score (0-100)</span>{badge("AKTİF", "OK")}</div>
          <div class="item"><span>Top 13 Etsy Tag Madenciliği</span>{badge("AKTİF", "OK")}</div>
        </div>
        <div class="pipe"></div>
        <div class="box">
          <div class="head"><span class="dot"></span> 3. Load (Çıktılar)</div>
          <div class="item"><span>CSV & Dashboard Veri</span>{badge("GÜNCEL", "OK")}</div>
          <div class="item"><span>Google Sheets Sync</span>{badge("BEKLEMEDE" if not get_secret("GOOGLE_SHEET_ID") else "AKTİF", "PENDING" if not get_secret("GOOGLE_SHEET_ID") else "OK")}</div>
          <div class="item"><span>GitHub Cron (TSİ 04:00)</span>{badge("HAZIR", "OK")}</div>
        </div>
      </div>
    </body></html>"""
    components.html(html, height=275)


def render_scorecard_visuals(df: pd.DataFrame) -> None:
    """Renders matching dark-slate horizontal bar chart and styled scorecard table."""
    if df.empty:
        st.info("Filtreye uygun niş bulunamadı.")
        return

    bars_html = ""
    rows_html = ""
    for _, r in df.head(20).iterrows():
        niche = escape(str(r["niche"]))
        score = float(r.get("opportunity_score", 0))
        seed = escape(str(r.get("seed_category", "-")))
        t_type = escape(str(r.get("trend_type", "-")))
        growth = r.get("growth_pct", "-")
        comp_raw = r.get("total_competition", "Pending Etsy API")
        price_raw = r.get("avg_price_usd", "Pending Etsy API")

        comp_str = f"{int(comp_raw):,}" if isinstance(comp_raw, (int, float)) and pd.notna(comp_raw) and str(comp_raw).isdigit() else escape(str(comp_raw))
        price_str = f"${float(price_raw):.2f}" if isinstance(price_raw, (int, float)) and pd.notna(price_raw) else escape(str(price_raw))
        growth_str = f"+{int(growth)}%" if str(t_type) == "RISING" and str(growth).lstrip("-").isdigit() else str(growth)

        bar_color = "#22c55e" if score >= 70 else ("#f97316" if score >= 45 else "#ef4444")
        score_cls = "ok" if score >= 70 else ("mid" if score >= 45 else "missing")

        bars_html += f"""
        <div class="bar-row">
          <div class="bar-meta">
            <span class="bar-name">{niche}</span>
            <strong style="color:{bar_color};">{score:.1f} / 100</strong>
          </div>
          <div class="bar-track">
            <div class="bar-fill" style="width:{min(100, max(0, score))}%; background:{bar_color};"></div>
          </div>
        </div>
        """

        rows_html += f"""
        <tr>
          <td><strong>{niche}</strong><br/><span style="color:#64748b;font-size:11px;">{seed}</span></td>
          <td><span class="badge {score_cls}">{score:.1f}</span></td>
          <td><span class="badge {'ok' if t_type=='RISING' else 'pending'}">{t_type} ({growth_str})</span></td>
          <td style="color:#94a3b8;">{comp_str}</td>
          <td style="color:#94a3b8;">{price_str}</td>
        </tr>
        """

    height = max(320, 140 + min(len(df), 20) * 54)
    html = f"""<!DOCTYPE html><html><head><style>
    {BASE_CSS}
    .grid {{
      display: grid;
      grid-template-columns: 1fr 1.35fr;
      gap: 16px;
    }}
    .title {{
      font-size: 14px;
      font-weight: 700;
      margin-bottom: 14px;
      color: #f8fafc;
    }}
    .bar-row {{ margin-bottom: 13px; }}
    .bar-row:last-child {{ margin-bottom: 0; }}
    .bar-meta {{
      display: flex;
      justify-content: space-between;
      font-size: 13px;
      margin-bottom: 5px;
    }}
    .bar-name {{ color: #e2e8f0; font-weight: 600; }}
    .bar-track {{
      height: 11px;
      background: #1b2742;
      border-radius: 999px;
      overflow: hidden;
    }}
    .bar-fill {{
      height: 100%;
      border-radius: 999px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th, td {{
      text-align: left;
      padding: 10px 10px;
      font-size: 13px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.16);
    }}
    th {{
      color: #94a3b8;
      font-size: 11.5px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    tr:last-child td {{ border-bottom: none; }}
    @media (max-width: 850px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
    </style></head><body>
      <div class="grid">
        <div class="card">
          <div class="title">Canlı Keşfedilen Trendler — Fırsat Skoru (0–100)</div>
          {bars_html}
        </div>
        <div class="card">
          <div class="title">Dinamik Trend & Rekabet Tablosu</div>
          <table>
            <thead>
              <tr>
                <th>Keşfedilen Arama</th>
                <th>Skor</th>
                <th>Google Trends</th>
                <th>Etsy Rekabet</th>
                <th>Etsy Fiyat</th>
              </tr>
            </thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>
      </div>
    </body></html>"""
    components.html(html, height=height)


def render_api_status_table() -> None:
    """Renders dark-slate API readiness table matching the ETL design language."""
    apis = [
        ("Gelato Satıcı API", "HAZIR" if get_secret("GELATO_API_KEY") else "EKSİK", "ok" if get_secret("GELATO_API_KEY") else "missing", "Ürün maliyeti & katalog çekimi"),
        ("Google Trends (pytrends)", "CANLI", "ok", "90 günlük arama ivmesi (API key gerekmez)"),
        ("Pinterest Trends API v5", "AKTİF" if get_secret("PINTEREST_ACCESS_TOKEN") else "ONAY BEKLİYOR", "ok" if get_secret("PINTEREST_ACCESS_TOKEN") else "pending", "Trial access başvurusu gönderildi; onay bekleniyor"),
        ("Etsy Open API v3", "AKTİF" if get_secret("ETSY_API_KEY") else "MAĞAZA BEKLİYOR", "ok" if get_secret("ETSY_API_KEY") else "missing", "TR'den Etsy mağazası açılınca Seller App ile alınacak"),
        ("Google Sheets Sync", "AKTİF" if get_secret("GOOGLE_SHEET_ID") else "KURULUM BEKLİYOR", "ok" if get_secret("GOOGLE_SHEET_ID") else "pending", "Ortak Google Sheet bağlantısı için Service Account gerekir"),
        ("eBay Browse & Reddit", "OPSİYONEL", "pending", "Çapraz fiyat ve niş fikir madenciliği için ek kaynak"),
    ]
    rows = "".join(
        f'<tr><td><strong>{escape(a)}</strong></td><td><span class="badge {cls}">{escape(st_txt)}</span></td><td style="color:#94a3b8;">{escape(note)}</td></tr>'
        for a, st_txt, cls, note in apis
    )
    html = f"""<!DOCTYPE html><html><head><style>
    {BASE_CSS}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 9px 10px; font-size: 13px; border-bottom: 1px solid rgba(148,163,184,0.16); }}
    th {{ color: #94a3b8; font-size: 11.5px; text-transform: uppercase; }}
    tr:last-child td {{ border-bottom: none; }}
    </style></head><body>
      <div class="card">
        <table>
          <thead><tr><th>API Kaynağı</th><th>Durum</th><th>Açıklama</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </body></html>"""
    components.html(html, height=285)


@st.cache_data(ttl=3600)
def fetch_yearly_seasonality(keywords: tuple[str, ...]) -> tuple[pd.DataFrame, str | None]:
    """Fetches 12-month (52-week) Google Trends interest for up to 4 keywords."""
    if not keywords:
        return pd.DataFrame(), None
    try:
        from pytrends.request import TrendReq

        kw_list = list(keywords[:4])
        pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 25))
        pytrends.build_payload(kw_list, cat=0, timeframe="today 12-m", geo="US")
        df = pytrends.interest_over_time()
        if df.empty:
            return pd.DataFrame(), "Google Trends bu kelimeler için 12 aylık veri döndürmedi."
        if "isPartial" in df.columns:
            df = df.drop(columns=["isPartial"])
        return df, None
    except Exception as exc:
        return pd.DataFrame(), f"Google Trends 12 aylık veri çekilemedi (rate-limit olabilir): {exc}"


def render_seasonality_chart(df: pd.DataFrame) -> None:
    """Renders a sleek dark-slate multi-line SVG chart for 12-month seasonality."""
    if df.empty:
        return

    colors = ["#22c55e", "#f97316", "#38bdf8", "#eab308"]
    cols = list(df.columns)[:4]
    dates = [d.strftime("%b %y") if hasattr(d, "strftime") else str(d) for d in df.index]
    n = len(dates)
    if n < 2:
        return

    width, height = 960, 280
    pad_l, pad_r, pad_t, pad_b = 42, 20, 20, 36
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    grid_svg = ""
    for val in (0, 25, 50, 75, 100):
        y = pad_t + plot_h - (val / 100.0) * plot_h
        grid_svg += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" stroke="rgba(148,163,184,0.14)" stroke-dasharray="4 4"/>'
        grid_svg += f'<text x="{pad_l - 8}" y="{y + 4:.1f}" fill="#64748b" font-size="11" text-anchor="end">{val}</text>'

    # X-axis month labels (every ~4 weeks)
    step = max(1, n // 10)
    x_labels_svg = ""
    for i in range(0, n, step):
        x = pad_l + (i / (n - 1)) * plot_w
        x_labels_svg += f'<text x="{x:.1f}" y="{height - 10}" fill="#94a3b8" font-size="11" text-anchor="middle">{escape(dates[i])}</text>'

    paths_svg = ""
    legend_html = ""
    peaks_html = ""

    for idx, col in enumerate(cols):
        c = colors[idx % len(colors)]
        vals = df[col].astype(float).tolist()
        pts = []
        for i, v in enumerate(vals):
            x = pad_l + (i / (n - 1)) * plot_w
            y = pad_t + plot_h - (min(100.0, max(0.0, v)) / 100.0) * plot_h
            pts.append(f"{x:.1f},{y:.1f}")
        paths_svg += f'<polyline fill="none" stroke="{c}" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round" points="{" ".join(pts)}"/>'

        max_val = max(vals)
        peak_idx = vals.index(max_val)
        peak_date = dates[peak_idx]
        avg_val = sum(vals) / len(vals)
        legend_html += f'<span style="display:inline-flex;align-items:center;gap:6px;margin-right:16px;font-size:12.5px;"><span style="width:10px;height:10px;border-radius:50%;background:{c};"></span><strong>{escape(col)}</strong></span>'
        peaks_html += f'<div class="peak-pill"><span style="color:{c};font-weight:700;">{escape(col)}</span><span>Zirve: <strong>{escape(peak_date)}</strong> (Skor {int(max_val)} | Ort {avg_val:.0f})</span></div>'

    html = f"""<!DOCTYPE html><html><head><style>
    {BASE_CSS}
    .legend {{ display:flex; flex-wrap:wrap; margin-bottom:10px; }}
    .peaks {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:10px; margin-top:12px; }}
    .peak-pill {{
      background:#1b2742; border:1px solid rgba(148,163,184,0.18); border-radius:9px;
      padding:8px 12px; font-size:12px; display:flex; flex-direction:column; gap:3px;
    }}
    svg {{ width:100%; height:auto; display:block; }}
    </style></head><body>
      <div class="card">
        <div class="legend">{legend_html}</div>
        <svg viewBox="0 0 {width} {height}">
          {grid_svg}
          {x_labels_svg}
          {paths_svg}
        </svg>
        <div class="peaks">{peaks_html}</div>
      </div>
    </body></html>"""
    components.html(html, height=400)


def main() -> None:
    if "force_live" not in st.session_state:
        st.session_state.force_live = False

    sc_df, wt_df, source_label = load_dashboard_data(force_live=st.session_state.force_live)

    col_title, col_btn = st.columns([3.5, 1.5])
    with col_title:
        st.title("📊 POD & Etsy — Canlı Ekip Dashboard")
        st.caption(f"Veri Kaynağı: **{source_label}** • Tüm ekip (Sen, Reyna, TR Mağaza) için ortak takip ekranı")
    with col_btn:
        if st.button("🔄 Canlı Tara (Google Trends)", use_container_width=True):
            st.cache_data.clear()
            st.session_state.force_live = True
            st.rerun()

    if sc_df.empty:
        st.info("Henüz niş verisi bulunmuyor.")
        return

    latest_date = str(sc_df["date"].max()) if "date" in sc_df.columns else "-"
    latest_df = sc_df[sc_df["date"].astype(str) == latest_date].copy() if "date" in sc_df.columns else sc_df.copy()

    k1, k2, k3, k4 = st.columns(4)
    top_row = latest_df.sort_values("opportunity_score", ascending=False).iloc[0]
    k1.metric("Son Çalışma Tarihi", latest_date, "Sistem Güncel")
    k2.metric("Keşfedilen Trend", len(latest_df))
    k3.metric("En Yüksek Skor", f"{top_row['opportunity_score']} / 100", str(top_row["niche"]))
    numeric_prices = pd.to_numeric(latest_df.get("avg_price_usd"), errors="coerce").dropna()
    k4.metric("Ortalama Etsy Fiyatı", f"${numeric_prices.mean():.2f}" if not numeric_prices.empty else "Pending Etsy API", "Hedef: $24+")

    st.subheader("⚙️ Canlı ETL Akış Durumu (Extract → Transform → Load)")
    api_states = {
        "Gelato Catalog API": ("AKTİF" if get_secret("GELATO_API_KEY") else "EKSİK", "OK" if get_secret("GELATO_API_KEY") else "MISSING"),
        "Google Trends (90g)": ("AKTİF (Keysiz)", "OK"),
        "Pinterest Trends v5": ("AKTİF" if get_secret("PINTEREST_ACCESS_TOKEN") else "ONAY BEKLİYOR", "OK" if get_secret("PINTEREST_ACCESS_TOKEN") else "PENDING"),
        "Etsy Open API v3": ("AKTİF" if get_secret("ETSY_API_KEY") else "MAĞAZA BEKLİYOR", "OK" if get_secret("ETSY_API_KEY") else "MISSING"),
        "eBay & Reddit API": ("AKTİF" if get_secret("EBAY_ACCESS_TOKEN") else "OPSİYONEL", "OK" if get_secret("EBAY_ACCESS_TOKEN") else "PENDING"),
    }
    render_animated_etl_flow(api_states)

    with st.expander("🔑 Eksik veya Onay Sürecindeki API'ler (Takım Durumu)", expanded=False):
        render_api_status_table()

    st.subheader("📈 Niş Skorları & Sonuç Tablosu")
    c_filter1, c_filter2 = st.columns([2, 1])
    with c_filter1:
        search_q = st.text_input("Niş Ara", placeholder="Örn: planner, vision, tennis...")
    with c_filter2:
        min_score = st.slider("Minimum Fırsat Skoru", 0, 100, 0)

    filtered = latest_df[
        (latest_df["opportunity_score"] >= min_score)
        & (latest_df["niche"].astype(str).str.lower().str.contains(search_q.lower().strip()))
    ].sort_values("opportunity_score", ascending=False)

    render_scorecard_visuals(filtered)

    st.subheader("📅 12 Aylık Mevsimsellik (Seasonality) Analizi")
    st.caption("Seçtiğin nişlerin son 12 ayda (52 hafta) hangi aylarda zirve yaptığını canlı Google Trends üzerinden karşılaştır.")
    all_niches = latest_df["niche"].astype(str).tolist()
    default_picks = all_niches[:3] if len(all_niches) >= 3 else all_niches
    selected_season_niches = st.multiselect(
        "Karşılaştırılacak Nişler (En fazla 4 adet)",
        options=all_niches,
        default=default_picks,
        max_selections=4,
    )
    if selected_season_niches:
        season_df, season_err = fetch_yearly_seasonality(tuple(selected_season_niches))
        if season_err:
            st.warning(season_err)
        else:
            render_seasonality_chart(season_df)

    st.subheader("🏷️ Reyna İçin Hazır Etiketler (Winning Tags)")
    niche_options = filtered["niche"].tolist() if not filtered.empty else latest_df["niche"].tolist()
    selected_niche = st.selectbox("Niş Seç", niche_options)
    if selected_niche and not wt_df.empty and "niche" in wt_df.columns:
        niche_tags = wt_df[wt_df["niche"] == selected_niche].sort_values("frequency", ascending=False)
        tags_list = niche_tags["tag"].astype(str).tolist()[:13]
        st.write("Etsy'ye doğrudan yapıştırmak için (sağ üstten kopyala):")
        st.code(", ".join(tags_list), language=None)
    else:
        st.info("Etsy Winning Tags verisi `ETSY_API_KEY` eklendiğinde otomatik dolacaktır.")


if __name__ == "__main__":
    main()
