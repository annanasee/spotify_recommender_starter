"""
create_playlists.py
Tworzy prywatne playlisty z rekomendacji:
- data/processed/recs_history.csv  -> "Recs – Historia"
- data/processed/recs_prefs.csv    -> "Recs – Preferencje"
"""

import os
import datetime as dt
import pandas as pd
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException

load_dotenv()

DATA_PROC = "data/processed"
# Potrzebujemy prawa do tworzenia prywatnych playlist + odczyt profilu (ID)
SCOPE = "playlist-modify-private user-read-private"

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

def read_tracks_csv(path: str) -> list[str]:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return []
    df = pd.read_csv(path, encoding="utf-8")
    if "track_id" not in df.columns:
        return []
    ids = [str(x) for x in df["track_id"].dropna().tolist() if str(x).strip()]
    # na URIs:
    return [f"spotify:track:{tid}" for tid in ids]

def chunked(xs, n=100):
    for i in range(0, len(xs), n):
        yield xs[i:i+n]

def ensure_playlist(sp: spotipy.Spotify, user_id: str, name: str, description: str) -> str:
    """Zawsze tworzy NOWĄ playlistę (łatwiej porównywać wyniki)."""
    pl = sp.user_playlist_create(
        user=user_id,
        name=name,
        public=False,
        description=description[:300]
    )
    return pl["id"]

def fill_playlist(sp: spotipy.Spotify, playlist_id: str, uris: list[str]) -> None:
    for batch in chunked(uris, 100):
        if batch:
            sp.playlist_add_items(playlist_id, batch)

def main():
    sp = sp_user()
    me = sp.current_user()
    user_id = me["id"]

    uris_hist = read_tracks_csv(f"{DATA_PROC}/recs_history.csv")
    uris_prefs = read_tracks_csv(f"{DATA_PROC}/recs_prefs.csv")

    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    if uris_hist:
        pid = ensure_playlist(
            sp, user_id,
            name=f"Recs – Historia ({ts})",
            description="Automatycznie wygenerowane z profilu historii (by_related)."
        )
        fill_playlist(sp, pid, uris_hist)
        print(f"✅ Utworzono playlistę: Recs – Historia ({ts})  ({len(uris_hist)} utworów)")

    if uris_prefs:
        pid = ensure_playlist(
            sp, user_id,
            name=f"Recs – Preferencje ({ts})",
            description="Automatycznie wygenerowane z zapisanych utworów (by_related)."
        )
        fill_playlist(sp, pid, uris_prefs)
        print(f"✅ Utworzono playlistę: Recs – Preferencje ({ts})  ({len(uris_prefs)} utworów)")

    if not uris_hist and not uris_prefs:
        print("⚠️  Brak CSV z rekomendacjami. Uruchom najpierw make_recs.py")

if __name__ == "__main__":
    main()
