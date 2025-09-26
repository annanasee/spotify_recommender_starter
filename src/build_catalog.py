"""
build_catalog.py
Łączy dane z data/raw w jeden katalog utworów + buduje profil użytkownika
oparty o artystów i gatunki (bez audio-features).

Wejście (data/raw):
- saved_tracks.csv
- top_tracks.csv
- recently_played.csv
- artists.csv

Wyjście (data/processed):
- catalog.csv              (scalona tabela utworów + metadane artysty)
- profile.json             (Top artyści/gatunki jako seedy pod rekomendacje)
- profile_preview.csv      (podgląd rozkładu gatunków i artystów)
"""

import os
import json
import pandas as pd
from collections import Counter

RAW = "data/raw"
PROCESSED = "data/processed"

def safe_read_csv(path: str) -> pd.DataFrame:
    try:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return pd.read_csv(path, encoding="utf-8")
    except Exception:
        pass
    return pd.DataFrame()

def main():
    os.makedirs(PROCESSED, exist_ok=True)

    saved   = safe_read_csv(f"{RAW}/saved_tracks.csv")
    top     = safe_read_csv(f"{RAW}/top_tracks.csv")
    recent  = safe_read_csv(f"{RAW}/recently_played.csv")
    artists = safe_read_csv(f"{RAW}/artists.csv")

    # Normalizacja kolumn
    for df in (saved, top, recent):
        if not df.empty:
            for col in ["track_id","name","artist_id","artist_name","album"]:
                if col in df.columns:
                    df[col] = df[col].astype(str)

    # Źródła i wagi
    if not saved.empty:
        saved["source"] = "saved"
        saved["weight"] = 1.0
    if not top.empty:
        top["source"] = "top"
        if "time_range" in top.columns:
            top["weight"] = top["time_range"].map(
                {"short_term": 2.0, "medium_term": 1.6, "long_term": 1.3}
            ).fillna(1.5)
        else:
            top["weight"] = 1.5
    if not recent.empty:
        recent["source"] = "recent"
        recent["weight"] = 2.2  # ostatnie odsłuchy bardziej ważą

    frames = [df for df in (saved, top, recent) if not df.empty]
    if len(frames) == 0:
        print("⚠️  Brak danych wejściowych w data/raw/. Uruchom najpierw fetch_api.py")
        return

    all_rows = pd.concat(frames, ignore_index=True)

    # Merge metadanych artysty
    if not artists.empty:
        arts = artists.copy()
        for col in ["genres","artist_name","artist_id","artist_popularity","followers"]:
            if col in arts.columns:
                arts[col] = arts[col].fillna("")
        all_rows = all_rows.merge(
            arts[["artist_id","genres","artist_popularity","followers","artist_name"]].drop_duplicates("artist_id"),
            on="artist_id", how="left", suffixes=("","_from_art")
        )
        if "artist_name_from_art" in all_rows.columns:
            all_rows["artist_name"] = all_rows["artist_name"].fillna(all_rows["artist_name_from_art"])
            all_rows.drop(columns=["artist_name_from_art"], inplace=True, errors="ignore")
    else:
        for col in ["genres","artist_popularity","followers"]:
            if col not in all_rows.columns:
                all_rows[col] = ""

    # Katalog – porządkowanie
    keep_cols = [
        "track_id","name","artist_id","artist_name","album","popularity",
        "source","time_range","played_at","added_at",
        "genres","artist_popularity","followers","weight"
    ]
    for c in keep_cols:
        if c not in all_rows.columns:
            all_rows[c] = None

    all_rows["weight"] = all_rows["weight"].fillna(1.0)
    all_rows = (all_rows
                .sort_values(["track_id","weight"], ascending=[True, False])
                .drop_duplicates(subset=["track_id"], keep="first"))

    os.makedirs(PROCESSED, exist_ok=True)
    all_rows.to_csv(f"{PROCESSED}/catalog.csv", index=False, encoding="utf-8")
    print(f"✔️  Zapisano {PROCESSED}/catalog.csv  ({len(all_rows)} utworów)")

    # --------- Profil (artyści + gatunki) ----------
    def split_genres(x):
        if pd.isna(x) or not isinstance(x, str) or x.strip() == "":
            return []
        return [g.strip() for g in x.split(",") if g.strip()]

    from collections import Counter
    genre_counter = Counter()
    artist_counter = Counter()

    for _, row in all_rows.iterrows():
        w = float(row.get("weight", 1.0) or 1.0)
        a_id = row.get("artist_id")
        a_nm = row.get("artist_name") or ""
        if a_id:
            artist_counter[(a_id, a_nm)] += w
        for g in split_genres(row.get("genres", "")):
            genre_counter[g] += w

    top_artists = [{"artist_id": aid, "artist_name": anm, "score": float(score)}
                   for (aid, anm), score in artist_counter.most_common(15)]
    top_genres  = [{"genre": g, "score": float(score)} for g, score in genre_counter.most_common(20)]

    profile = {
        "seeds": {
            "artist_ids": [a["artist_id"] for a in top_artists[:5]],
            "genres": [g["genre"] for g in top_genres[:5]],
        },
        "top_artists": top_artists,
        "top_genres": top_genres,
        "counts": {
            "tracks": int(len(all_rows)),
            "unique_artists": int(all_rows["artist_id"].nunique()),
            "unique_genres": int(len(genre_counter)),
        },
    }

    with open(f"{PROCESSED}/profile.json", "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    preview_rows = []
    for a in top_artists:
        preview_rows.append({"type": "artist", "id_or_name": a["artist_name"], "score": a["score"]})
    for g in top_genres:
        preview_rows.append({"type": "genre", "id_or_name": g["genre"], "score": g["score"]})
    pd.DataFrame(preview_rows).to_csv(f"{PROCESSED}/profile_preview.csv", index=False, encoding="utf-8")

    print(f"✔️  Zapisano {PROCESSED}/profile.json oraz {PROCESSED}/profile_preview.csv")
    print("✅  Profil gotowy – można generować rekomendacje na bazie historii.")

if __name__ == "__main__":
    main()

