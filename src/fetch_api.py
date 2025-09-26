"""
fetch_api.py
Pobiera dane użytkownika do rekomendacji:
- saved tracks, top tracks (3 zakresy), recently played
- artists (z gatunkami)
Zapisuje do data/raw/*.csv

Uwaga: NIE pobieramy audio-features (endpoint zablokowany w dev).
"""

import os
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

import pandas as pd
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException

# ------------------------ Konfiguracja ------------------------

load_dotenv()

SCOPE = "user-library-read user-top-read user-read-recently-played"
DATA_RAW = "data/raw"

# ------------------------ Modele danych -----------------------

@dataclass
class TrackLite:
    track_id: str
    name: str
    artist_id: Optional[str]
    artist_name: Optional[str]
    album: Optional[str]
    popularity: int

# ------------------------ Pomocnicze --------------------------

def auth_user_client() -> spotipy.Spotify:
    """Klient użytkownika (OAuth) – do saved/top/recent i artists."""
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

def simplify_track(t: Dict[str, Any]) -> TrackLite:
    arts = t.get("artists", []) or []
    main = arts[0] if arts else {"id": None, "name": None}
    return TrackLite(
        track_id=t.get("id"),
        name=t.get("name"),
        artist_id=main.get("id"),
        artist_name=main.get("name"),
        album=(t.get("album") or {}).get("name"),
        popularity=int(t.get("popularity") or 0),
    )

# ------------------------ Pobieranie danych -------------------

def fetch_saved_tracks(sp: spotipy.Spotify) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    try:
        results = sp.current_user_saved_tracks(limit=50)
    except SpotifyException as e:
        print(f"⚠️  saved_tracks: błąd startowy: {e}")
        return pd.DataFrame(rows)

    while True:
        for it in results.get("items", []):
            tr = it.get("track")
            if not tr:
                continue
            d = simplify_track(tr).__dict__.copy()
            d["added_at"] = it.get("added_at")
            rows.append(d)
        if results.get("next"):
            try:
                results = sp.next(results)
            except SpotifyException as e:
                print(f"⚠️  saved_tracks: kolejna strona: {e}")
                break
        else:
            break
    return pd.DataFrame(rows)

def fetch_top_tracks(sp: spotipy.Spotify) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for term in ("short_term", "medium_term", "long_term"):
        try:
            resp = sp.current_user_top_tracks(limit=50, time_range=term)
        except SpotifyException as e:
            print(f"⚠️  top_tracks {term}: {e}")
            resp = {"items": []}
        for tr in resp.get("items", []):
            d = simplify_track(tr).__dict__.copy()
            d["time_range"] = term
            rows.append(d)
    return pd.DataFrame(rows)

def fetch_recently_played(sp: spotipy.Spotify) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    try:
        res = sp.current_user_recently_played(limit=50)
    except SpotifyException as e:
        print(f"⚠️  recently_played: {e}")
        return pd.DataFrame(rows)

    for it in res.get("items", []):
        tr = it.get("track")
        if not tr:
            continue
        d = simplify_track(tr).__dict__.copy()
        d["played_at"] = it.get("played_at")
        rows.append(d)
    return pd.DataFrame(rows)

def fetch_artists(sp: spotipy.Spotify, artist_ids: List[str]) -> pd.DataFrame:
    artist_ids = list({a for a in artist_ids if a})
    rows: List[Dict[str, Any]] = []
    for i in range(0, len(artist_ids), 50):
        chunk = artist_ids[i : i + 50]
        try:
            arts = sp.artists(chunk).get("artists", [])
        except SpotifyException as e:
            print(f"⚠️  artists batch {i//50}: {e}")
            arts = []
        for a in arts:
            rows.append(
                {
                    "artist_id": a.get("id"),
                    "artist_name": a.get("name"),
                    "genres": ",".join(a.get("genres") or []),
                    "followers": (a.get("followers") or {}).get("total"),
                    "artist_popularity": a.get("popularity"),
                }
            )
    return pd.DataFrame(rows)

# ------------------------ Główny przebieg ---------------------

def main():
    os.makedirs(DATA_RAW, exist_ok=True)
    sp_user = auth_user_client()

    # 1) saved
    print("→ saved tracks…")
    saved = fetch_saved_tracks(sp_user)
    sample_path = f"{DATA_RAW}/saved_tracks_sample.csv"
    if saved.empty and os.path.exists(sample_path):
        print("ℹ️  Brak zapisanych utworów – używam próbki.")
        try:
            saved = pd.read_csv(sample_path, encoding="utf-8")
        except Exception as e:
            print("⚠️  nie udało się wczytać próbki:", e)
            saved = pd.DataFrame()
    saved.to_csv(f"{DATA_RAW}/saved_tracks.csv", index=False, encoding="utf-8")

    # 2) top
    print("→ top tracks…")
    top = fetch_top_tracks(sp_user)
    top.to_csv(f"{DATA_RAW}/top_tracks.csv", index=False, encoding="utf-8")

    # 3) recent
    print("→ recently played…")
    recent = fetch_recently_played(sp_user)
    recent.to_csv(f"{DATA_RAW}/recently_played.csv", index=False, encoding="utf-8")

    # 4) artists
    all_tracks = (
        pd.concat([saved, top, recent], ignore_index=True)
        if (not saved.empty) or (not top.empty) or (not recent.empty)
        else pd.DataFrame()
    )
    uniq_artist_ids = (
        all_tracks["artist_id"].dropna().unique().tolist()
        if not all_tracks.empty else []
    )
    print("→ artists (genres)…")
    artists = fetch_artists(sp_user, uniq_artist_ids)
    artists.to_csv(f"{DATA_RAW}/artists.csv", index=False, encoding="utf-8")

    print("Gotowe ✅ Pliki w data/raw/")

if __name__ == "__main__":
    main()


