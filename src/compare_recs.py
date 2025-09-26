"""
compare_recs.py
Porównuje dwie listy rekomendacji:
- data/processed/recs_history.csv
- data/processed/recs_prefs.csv

Liczy:
- liczność, unikalnych artystów
- nowość względem katalogu użytkownika (data/processed/catalog.csv)
- różnorodność gatunków (mapowane z data/raw/artists.csv)
- overlap (wspólne utwory) między listami

Wyniki:
- data/processed/recs_compare_summary.json   (zbiorcze metryki)
- data/processed/recs_compare_details.csv    (scalona tabela z flagami)
- data/processed/recs_overlap.csv            (lista wspólnych utworów)
"""

import os
import json
from collections import Counter
from typing import Dict, Any, List, Set

import pandas as pd

RAW = "data/raw"
PROC = "data/processed"

def safe_read_csv(path: str) -> pd.DataFrame:
    try:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return pd.read_csv(path, encoding="utf-8")
    except Exception:
        pass
    return pd.DataFrame()

def genres_map_from_artists(artists_df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Buduje mapę artist_id -> [genres], ignorując puste wartości i literalny 'nan'.
    """
    gm: Dict[str, List[str]] = {}
    if artists_df.empty:
        return gm
    for _, row in artists_df.iterrows():
        aid = str(row.get("artist_id"))
        val = row.get("genres")
        if pd.isna(val) or not isinstance(val, str) or not val.strip():
            glist: List[str] = []
        else:
            glist = [g.strip() for g in val.split(",")
                     if g.strip() and g.strip().lower() != "nan"]
        gm[aid] = glist
    return gm

def attach_flags(df: pd.DataFrame, list_name: str, seen_ids: Set[str], gmap: Dict[str, List[str]]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[
            "which","track_id","name","artist_id","artist_name","album","popularity",
            "in_catalog","genres_join"
        ])
    out = df.copy()
    out["which"] = list_name
    out["track_id"] = out["track_id"].astype(str)
    out["artist_id"] = out["artist_id"].astype(str)
    out["in_catalog"] = out["track_id"].isin(seen_ids)
    out["genres_join"] = out["artist_id"].map(lambda a: ", ".join(gmap.get(a, [])))
    return out

def diversity_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {"tracks": 0, "unique_artists": 0, "unique_genres": 0, "top_artists": [], "top_genres": []}
    uniq_art = int(df["artist_id"].nunique())
    genres_all: List[str] = []
    for s in df.get("genres_join", []):
        if not isinstance(s, str) or not s:
            continue
        genres_all.extend([g.strip() for g in s.split(",")
                           if g.strip() and g.strip().lower() != "nan"])
    c_gen = Counter(genres_all)
    c_art = Counter(df["artist_name"].fillna("").astype(str).tolist())
    top_art = [{"name": n, "count": int(c)} for n, c in c_art.most_common(5)]
    top_gen = [{"genre": g, "count": int(c)} for g, c in c_gen.most_common(5)]
    return {
        "tracks": int(len(df)),
        "unique_artists": uniq_art,
        "unique_genres": int(len(c_gen)),
        "top_artists": top_art,
        "top_genres": top_gen,
    }

def main():
    hist = safe_read_csv(f"{PROC}/recs_history.csv")
    prefs = safe_read_csv(f"{PROC}/recs_prefs.csv")
    catalog = safe_read_csv(f"{PROC}/catalog.csv")
    artists_df = safe_read_csv(f"{RAW}/artists.csv")

    if hist.empty and prefs.empty:
        print("⚠️  Brak rekomendacji do porównania. Najpierw uruchom make_recs.py")
        return

    seen_ids: Set[str] = set()
    if not catalog.empty:
        seen_ids = set(catalog["track_id"].dropna().astype(str).tolist())

    gmap = genres_map_from_artists(artists_df)

    hist_f = attach_flags(hist, "history", seen_ids, gmap)
    prefs_f = attach_flags(prefs, "prefs", seen_ids, gmap)

    # overlap
    overlap_ids = set(hist_f["track_id"]).intersection(set(prefs_f["track_id"]))
    overlap_df = pd.concat(
        [
            hist_f[hist_f["track_id"].isin(overlap_ids)],
            prefs_f[prefs_f["track_id"].isin(overlap_ids)],
        ],
        ignore_index=True,
    )

    # nowość
    hist_new = (~hist_f["in_catalog"]).sum()
    prefs_new = (~prefs_f["in_catalog"]).sum()

    # metryki różnorodności
    m_hist = diversity_metrics(hist_f)
    m_prefs = diversity_metrics(prefs_f)

    summary = {
        "history": {
            "tracks": m_hist["tracks"],
            "unique_artists": m_hist["unique_artists"],
            "unique_genres": m_hist["unique_genres"],
            "new_to_user_count": int(hist_new),
            "new_to_user_ratio": (int(hist_new) / max(1, m_hist["tracks"])) if m_hist["tracks"] else 0.0,
            "top_artists": m_hist["top_artists"],
            "top_genres": m_hist["top_genres"],
        },
        "prefs": {
            "tracks": m_prefs["tracks"],
            "unique_artists": m_prefs["unique_artists"],
            "unique_genres": m_prefs["unique_genres"],
            "new_to_user_count": int(prefs_new),
            "new_to_user_ratio": (int(prefs_new) / max(1, m_prefs["tracks"])) if m_prefs["tracks"] else 0.0,
            "top_artists": m_prefs["top_artists"],
            "top_genres": m_prefs["top_genres"],
        },
        "overlap": {
            "tracks": int(len(overlap_ids)),
            "ratio_vs_history": (len(overlap_ids) / max(1, m_hist["tracks"])) if m_hist["tracks"] else 0.0,
            "ratio_vs_prefs": (len(overlap_ids) / max(1, m_prefs["tracks"])) if m_prefs["tracks"] else 0.0,
        },
    }

    os.makedirs(PROC, exist_ok=True)
    with open(f"{PROC}/recs_compare_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    details = pd.concat([hist_f, prefs_f], ignore_index=True)
    details.to_csv(f"{PROC}/recs_compare_details.csv", index=False, encoding="utf-8")
    overlap_df.to_csv(f"{PROC}/recs_overlap.csv", index=False, encoding="utf-8")

    print("📊 Porównanie zapisane.")
    print("→ data/processed/recs_compare_summary.json")
    print("→ data/processed/recs_compare_details.csv")
    print("→ data/processed/recs_overlap.csv")

if __name__ == "__main__":
    main()
