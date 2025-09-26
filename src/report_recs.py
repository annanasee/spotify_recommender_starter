"""
report_recs.py
Tworzy:
- data/processed/recs_report.html  (ładny raport do przeglądarki)
- data/processed/recs_report.xlsx  (arkusze: summary, history, prefs, details, overlap)
Na podstawie plików:
- data/processed/recs_history.csv
- data/processed/recs_prefs.csv
- data/processed/recs_compare_details.csv
- data/processed/recs_overlap.csv
- data/processed/recs_compare_summary.json
"""

import os
import json
import pandas as pd

PROC = "data/processed"

def safe_read_csv(path: str) -> pd.DataFrame:
    try:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return pd.read_csv(path, encoding="utf-8")
    except Exception:
        pass
    return pd.DataFrame()

def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def make_summary_df(summary: dict) -> pd.DataFrame:
    rows = []
    for which in ["history", "prefs"]:
        s = summary.get(which, {})
        rows.append({
            "list": which,
            "tracks": s.get("tracks", 0),
            "unique_artists": s.get("unique_artists", 0),
            "unique_genres": s.get("unique_genres", 0),
            "new_to_user_count": s.get("new_to_user_count", 0),
            "new_to_user_ratio": round(s.get("new_to_user_ratio", 0.0), 3),
        })
    ov = summary.get("overlap", {})
    rows.append({
        "list": "overlap",
        "tracks": ov.get("tracks", 0),
        "unique_artists": "",
        "unique_genres": "",
        "new_to_user_count": "",
        "new_to_user_ratio": "",
    })
    return pd.DataFrame(rows)

def list_to_df(lst: list, cols: list) -> pd.DataFrame:
    if not isinstance(lst, list) or not lst:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(lst)[cols]

def render_html(summary_df: pd.DataFrame,
                top_art_hist: pd.DataFrame,
                top_gen_hist: pd.DataFrame,
                top_art_prefs: pd.DataFrame,
                top_gen_prefs: pd.DataFrame,
                hist: pd.DataFrame, prefs: pd.DataFrame,
                details: pd.DataFrame, overlap: pd.DataFrame,
                out_path: str) -> None:
    # Prosty styl
    css = """
    <style>
      body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; }
      h1 { margin-bottom: 0; }
      .muted { color:#666; margin-top:4px; }
      table { border-collapse: collapse; margin: 12px 0 24px 0; width: 100%; }
      th, td { border: 1px solid #ddd; padding: 8px; }
      th { background: #f7f7f7; text-align: left; }
      .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
      .section { margin: 24px 0; }
      .pill { display:inline-block; background:#eef; border:1px solid #ccd; padding:2px 8px; border-radius:999px; margin-right:6px; }
      .small { font-size: 12px; color:#444; }
    </style>
    """
    # Do HTML
    html = f"""
    <html><head><meta charset="utf-8"><title>Spotify Recs Report</title>{css}</head>
    <body>
      <h1>Raport rekomendacji</h1>
      <div class="muted small">Wygenerowano z CSV/JSON w data/processed</div>

      <div class="section">
        <h2>Podsumowanie</h2>
        {summary_df.to_html(index=False, escape=False)}
      </div>

      <div class="section grid">
        <div>
          <h3>Top artyści – Historia</h3>
          {top_art_hist.to_html(index=False, escape=False)}
        </div>
        <div>
          <h3>Top artyści – Preferencje</h3>
          {top_art_prefs.to_html(index=False, escape=False)}
        </div>
      </div>

      <div class="section grid">
        <div>
          <h3>Top gatunki – Historia</h3>
          {top_gen_hist.to_html(index=False, escape=False)}
        </div>
        <div>
          <h3>Top gatunki – Preferencje</h3>
          {top_gen_prefs.to_html(index=False, escape=False)}
        </div>
      </div>

      <div class="section">
        <h2>Lista – Historia</h2>
        {hist.to_html(index=False, escape=False)}
      </div>

      <div class="section">
        <h2>Lista – Preferencje</h2>
        {prefs.to_html(index=False, escape=False)}
      </div>

      <div class="section">
        <h2>Wspólne utwory (overlap)</h2>
        {"<div class='pill'>brak</div>" if overlap.empty else overlap.to_html(index=False, escape=False)}
      </div>

      <div class="section">
        <h2>Szczegóły (scalone)</h2>
        <div class="small muted">Zawiera flagi: which, in_catalog, genres_join</div>
        {details.to_html(index=False, escape=False)}
      </div>
    </body></html>
    """
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

def main():
    os.makedirs(PROC, exist_ok=True)

    # wejścia
    hist = safe_read_csv(f"{PROC}/recs_history.csv")
    prefs = safe_read_csv(f"{PROC}/recs_prefs.csv")
    details = safe_read_csv(f"{PROC}/recs_compare_details.csv")
    overlap = safe_read_csv(f"{PROC}/recs_overlap.csv")
    summary = load_json(f"{PROC}/recs_compare_summary.json")

    # małe porządki kolumn
    for df in [hist, prefs, details, overlap]:
        for col in ["track_id","name","artist_id","artist_name","album","popularity"]:
            if col in df.columns:
                df[col] = df[col].astype(str)

    # sekcje top z JSON
    hist_top_art = summary.get("history", {}).get("top_artists", [])
    hist_top_gen = summary.get("history", {}).get("top_genres", [])
    pref_top_art = summary.get("prefs", {}).get("top_artists", [])
    pref_top_gen = summary.get("prefs", {}).get("top_genres", [])

    top_art_hist = list_to_df(hist_top_art, ["name","count"])
    top_gen_hist = list_to_df(hist_top_gen, ["genre","count"])
    top_art_prefs = list_to_df(pref_top_art, ["name","count"])
    top_gen_prefs = list_to_df(pref_top_gen, ["genre","count"])

    summary_df = make_summary_df(summary)

    # HTML
    out_html = f"{PROC}/recs_report.html"
    render_html(summary_df, top_art_hist, top_gen_hist, top_art_prefs, top_gen_prefs,
                hist, prefs, details, overlap, out_html)

    # Excel
    out_xlsx = f"{PROC}/recs_report.xlsx"
    with pd.ExcelWriter(out_xlsx, engine="xlsxwriter") as xl:
        summary_df.to_excel(xl, sheet_name="summary", index=False)
        hist.to_excel(xl, sheet_name="history", index=False)
        prefs.to_excel(xl, sheet_name="prefs", index=False)
        details.to_excel(xl, sheet_name="details", index=False)
        overlap.to_excel(xl, sheet_name="overlap", index=False)

    print("✅ Raporty zapisane:")
    print(f"→ {out_html}")
    print(f"→ {out_xlsx}")

if __name__ == "__main__":
    main()
