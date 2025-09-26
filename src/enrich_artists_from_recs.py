"""
enrich_artists_from_recs.py
Uzupełnia data/raw/artists.csv o artystów z recs_history.csv i recs_prefs.csv,
pobierając ich metadane (name, genres, followers, popularity) z /artists (batch 50).
"""

import os
import pandas as pd
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from typing import List, Dict, Any

load_dotenv()

RAW = "data/raw"
PROC = "data/processed"
SCOPE = "user-read-private"  # wystarczy, korzystamy tylko z publicznego /artists

def sp_user() -> spotipy.Spotify:
    return spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            scope=SCOPE,
            client_id=os.getenv("SPOTIPY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
            redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
            open_browser=True,
            cache_path=".cache-spotify",
        )
    )

def safe_read_csv(path: str) -> pd.DataFrame:
    try:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return pd.read_csv(path, encoding="utf-8")
    except Exception:
        pass
    return pd.DataFrame()

def chunked(xs: List[str], n: int = 50):
    for i in range(0, len(xs), n):
        yield xs[i:i+n]

def main():
    os.makedirs(RAW, exist_ok=True)
    sp = sp_user()

    # 1) Zbierz artist_id z rekomendacji
    rec_h = safe_read_csv(f"{PROC}/recs_history.csv")
    rec_p = safe_read_csv(f"{PROC}/recs_prefs.csv")
    all_recs = pd.concat([rec_h, rec_p], ignore_index=True) if not rec_h.empty or not rec_p.empty else pd.DataFrame()

    if all_recs.empty or "artist_id" not in all_recs.columns:
        print("⚠️  Brak rekomendacji lub kolumny artist_id — najpierw uruchom make_recs.py")
        return

    target_artist_ids = set(all_recs["artist_id"].dropna().astype(str).tolist())

    # 2) Wczytaj istniejące artists.csv, aby pominąć już znanych
    artists_df = safe_read_csv(f"{RAW}/artists.csv")
    have_ids = set(artists_df["artist_id"].astype(str).tolist()) if not artists_df.empty and "artist_id" in artists_df.columns else set()
    missing = sorted(list(target_artist_ids - have_ids))

    if not missing:
        print("✅ Brak brakujących artystów — nic do wzbogacenia.")
        return

    # 3) Pobierz /artists w paczkach
    new_rows = []
    fetched = 0
    for batch in chunked(missing, 50):
        try:
            data = sp.artists(batch)
            arts = data.get("artists", []) or []
        except SpotifyException as e:
            print(f"⚠️  Błąd przy batchu ({len(batch)}): {e}")
            arts = []
        for a in arts:
            new_rows.append({
                "artist_id": a.get("id"),
                "artist_name": a.get("name"),
                "genres": ",".join(a.get("genres") or []),
                "followers": (a.get("followers") or {}).get("total"),
                "artist_popularity": a.get("popularity"),
            })
        fetched += len(batch)

    new_df = pd.DataFrame(new_rows)
    if new_df.empty:
        print("⚠️  Nie udało się pobrać metadanych dla brakujących artystów.")
        return

    # 4) Scal i zapisz
    out = (pd.concat([artists_df, new_df], ignore_index=True)
             if not artists_df.empty else new_df)
    out = (out.sort_values(["artist_id", "artist_popularity"], ascending=[True, False])
             .drop_duplicates("artist_id", keep="first"))

    out.to_csv(f"{RAW}/artists.csv", index=False, encoding="utf-8")

    print(f"✅ Dodano {len(new_df)} nowych artystów (łącznie: {len(out)}) i zapisano do {RAW}/artists.csv")

if __name__ == "__main__":
    main()
