"""
Weekly Digest Generator
=======================
Compares the latest 2 snapshots in pod_warehouse.db and highlights:
- Rising opportunities (sales & score up)
- Saturation warnings (competition jumping fast)
- Priority design briefs for Reyna
"""

from pathlib import Path
from db import DEFAULT_DB_PATH, get_latest_two_dates, get_snapshot_by_date


def generate_weekly_digest(db_path: Path = DEFAULT_DB_PATH, output_dir: Path | None = None) -> None:
    dates = get_latest_two_dates(db_path)
    if not dates:
        print("Veritabaninda henuz veri yok. Once keyword_etl.py calistirin.")
        return

    latest_date = dates[0]
    latest = get_snapshot_by_date(latest_date, db_path)
    prev_date = dates[1] if len(dates) > 1 else None
    prev = get_snapshot_by_date(prev_date, db_path) if prev_date else {}

    lines = [
        f"# Haftalık POD Keyword & Trend Raporu ({latest_date})",
        "",
        f"Karşılaştırılan önceki snapshot: **{prev_date or 'Yok (İlk Kayıt)'}**",
        "",
        "## 1. Güncel Durum & Haftalık Değişim (WoW)",
        "",
        "| Durum | Keyword | Skor | Skor Değişimi | Aylık Satış | Satış Değişimi | Net Kâr ($) | Rakip Değişimi |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    sorted_items = sorted(latest.values(), key=lambda x: x["opportunity_score"], reverse=True)
    rising = []
    warnings = []

    for item in sorted_items:
        kw = item["keyword"]
        old = prev.get(kw)
        if old:
            s_delta = round(item["opportunity_score"] - old["opportunity_score"], 2)
            sales_delta = round(item["avg_monthly_sales"] - old["avg_monthly_sales"], 1)
            comp_delta = item["total_results"] - old["total_results"]
            s_str = f"{s_delta:+.2f}"
            sales_str = f"{sales_delta:+.1f}"
            comp_str = f"{comp_delta:+d}"
            if sales_delta > 0 and s_delta >= 0:
                rising.append((kw, sales_delta, item["opportunity_score"]))
            if comp_delta >= 1000:
                warnings.append((kw, comp_delta))
        else:
            s_str = "NEW"
            sales_str = "NEW"
            comp_str = "NEW"

        lines.append(
            f"| {item['status']} | `{kw}` | {item['opportunity_score']} | {s_str} | "
            f"{item['avg_monthly_sales']} | {sales_str} | {item['est_net_profit_usd']} | {comp_str} |"
        )

    lines.extend(["", "## 2. Öne Çıkan Sinyaller", ""])
    if rising:
        lines.append("### Yükselen Fırsatlar (Rising)")
        for kw, sd, sc in rising:
            lines.append(f"- **{kw}**: Aylık satış tahmini `{sd:+.1f}` arttı (Skor: {sc})")
    else:
        lines.append("- Henüz önceki haftaya göre yükseliş verisi oluşmadı (2. hafta verisi bekleniyor).")

    if warnings:
        lines.append("\n### Doygunluk Uyarısı (Rekabet Hızla Artıyor)")
        for kw, cd in warnings:
            lines.append(f"- **{kw}**: Rakip ilan sayısı `{cd:+d}` arttı — farklılaşma şart.")

    out_path = (output_dir or Path(__file__).resolve().parent / "output") / f"weekly_report_{latest_date}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n[Weekly Digest] Rapor olusturuldu: {out_path}")
    print("\n".join(lines[5:13]))


if __name__ == "__main__":
    generate_weekly_digest()
