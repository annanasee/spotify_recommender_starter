"""
make_recs.py
Generuje 2 listy rekomendacji BEZ /recommendations:
- recs_history.csv  — z historii (top artyści z profile.json)
- recs_prefs.csv    — z preferencji (najczęściej zapisywani artyści z saved_tracks.csv)

Strategia:
- weź seedy (artystów) z profilu / zapisanych,
- (opcjonalnie) dla każdego seeda pobierz related-artists (1 hop),
- dla seeda oraz jego related pobierz /artists/{id}/top-tracks (market=PL),
- z każdego artysty weź max TOP_PER_ARTIST tracków, usuń duplikaty i to, co już masz,
- przytnij do TARGET_TRACKS.

Wyjścia:
- data/processed/recs_history.csv
- data/processed/recs_prefs.csv
- data/processed/recs_meta.json
"""

import os
import json
from typing import List, Dict, Any, Tuple, Set
from collections import Counter

import pandas as pd
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException

# ── Ścieżki i rynek ────────────────────────────────────────────────────────────
RAW = "data/raw"
PROC = "data/processed"
MARKET = "PL"

# ── Parametry sterujące (zmieniaj śmiało) ──────────────────────────────────────
SEEDS_HISTORY_MAX = 12          # ile seed artystów z historii
SEEDS_PREFS_MAX  = 12          # ile seed artystów z zapisanych
RELATED_PER_SEED = 12          # ilu powiązanych artystów bierzemy na 1 seed (0 = pomiń powiązanych)
TOP_PER_ARTIST   = 6           # ile top tracków na jednego artystę
TARGET_TRACKS    = 150         # cel na listę (po dedup i filtrze posiadanych)

# Scope nie wymaga dodatkowych uprawnień do odczytu publicznych endpointów
SCOPE = "user-read-private"

# ── Klient Spotify ─────────────────────────────────────────────────────────────
def sp_user() -> spotipy.Spotify:
    load_dotenv()
    return spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            scope=SCOPE,
            client_id=os.getenv("SPOTIPY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
            redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
            cache_path=".cache-spotify",
            open_browser=True,
        )
    )

# ── I/O helpers ────────────────────────────────────────────────────────────────
def safe_read_csv(path: str) -> pd.DataFrame:
    try:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return pd.read_csv(path, encoding="utf-8")
    except Exception:
        pass
    return pd.DataFrame()

def safe_read_json(path: str) -> Dict[str, Any]:
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# ── Seedy ──────────────────────────────────────────────────────────────────────
def pick_top_artists_from_profile(profile: Dict[str, Any], n: int) -> List[str]:
    """
    Z profile.json bierzemy 'top_artists' (posortowane), zwracamy listę artist_id.
    Fallback: jeśli brak, użyj seeds.artist_ids.
    """
    out: List[str] = []
    top = profile.get("top_artists") or []
    for item in top:
        aid = str(item.get("artist_id") or "").strip()
        if aid:
            out.append(aid)
    if not out:
        out = [str(x).strip() for x in (profile.get("seeds", {}).get("artist_ids") or []) if str(x).strip()]
    return out[:n]

def pick_top_artists_from_saved(saved_df: pd.DataFrame, n: int) -> List[str]:
    """
    Z saved_tracks.csv liczymy najczęstszych artystów.
    """
    if saved_df.empty or "artist_id" not in saved_df.columns:
        return []
    counts = Counter([str(a) for a in saved_df["artist_id"].dropna().astype(str).tolist()])
    return [aid for aid, _ in counts.most_common(n)]

# ── Spotify helpers ────────────────────────────────────────────────────────────
def get_related(sp: spotipy.Spotify, artist_id: str) -> List[Dict[str, Any]]:
    """
    Zwraca related artists (może być 404 w dev — wtedy zwraca []).
    """
    try:
        data = sp.artist_related_artists(artist_id)
        return data.get("artists", []) or []
    except SpotifyException as e:
        print(f"HTTP Error for related-artists({artist_id}): {e}")
        return []
    except Exception:
        return []

def get_top_tracks(sp: spotipy.Spotify, artist_id: str, market: str = MARKET) -> List[Dict[str, Any]]:
    try:
        data = sp.artist_top_tracks(artist_id, country=market)
        return data.get("tracks", []) or []
    except SpotifyException as e:
        print(f"HTTP Error for top-tracks({artist_id}): {e}")
        return []
    except Exception:
        return []

def tracks_from_artist(sp: spotipy.Spotify, artist_id: str, per_artist: int = TOP_PER_ARTIST) -> List[Dict[str, Any]]:
    tracks = get_top_tracks(sp, artist_id, MARKET)
    return tracks[:per_artist] if tracks else []

# ── Budowa wiersza i filtry ───────────────────────────────────────────────────
def as_row(track: Dict[str, Any], source: str) -> Dict[str, Any]:
    arts = track.get("artists") or []
    a0 = arts[0] if arts else {}
    return {
        "track_id": track.get("id"),
        "name": track.get("name"),
        "artist_id": a0.get("id"),
        "artist_name": a0.get("name"),
        "album": (track.get("album") or {}).get("name"),
        "popularity": track.get("popularity"),
        "source": source,
    }

def dedup_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for r in rows:
        tid = str(r.get("track_id") or "")
        if tid and tid not in seen:
            seen.add(tid)
            out.append(r)
    return out

def remove_owned(rows: List[Dict[str, Any]], catalog_df: pd.DataFrame) -> List[Dict[str, Any]]:
    if catalog_df.empty or "track_id" not in catalog_df.columns:
        return rows
    owned = set(catalog_df["track_id"].dropna().astype(str).tolist())
    return [r for r in rows if str(r.get("track_id") or "") not in owned]

# ── Generator listy dla seedów ────────────────────────────────────────────────
def gen_for_seeds(sp: spotipy.Spotify, seed_artist_ids: List[str], catalog_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Zbiera utwory dla listy seed artystów:
    - seed top tracks
    - (opcjonalnie) related artists (limit RELATED_PER_SEED) top tracks
    Filtruje, deduplikuje, tnie do TARGET_TRACKS.
    """
    rows: List[Dict[str, Any]] = []
    used_artists: Set[str] = set()

    total_seeds = len(seed_artist_ids)
    for i, seed in enumerate(seed_artist_ids, 1):
        print(f"→ seed {i}/{total_seeds}: {seed} …")

        # Top seed-artist
        for t in tracks_from_artist(sp, seed, TOP_PER_ARTIST):
            rows.append(as_row(t, source="seed_top"))

        # Related artists (1 hop) — dozwolone tylko gdy parametr > 0
        if RELATED_PER_SEED > 0:
            related = get_related(sp, seed)
            rel_ids = [a.get("id") for a in related if a.get("id")]
            rel_ids = rel_ids[:RELATED_PER_SEED]

            for rid in rel_ids:
                if rid in used_artists:
                    continue
                used_artists.add(rid)
                for t in tracks_from_artist(sp, rid, TOP_PER_ARTIST):
                    rows.append(as_row(t, source="by_related_top"))

        # wsteczna kontrola długości (nie twardy limit, tylko safety)
        if len(rows) >= TARGET_TRACKS * 2:
            break

    # dedup + usuń posiadane
    rows = dedup_rows(rows)
    rows = remove_owned(rows, catalog_df)

    # sortowanie: najpierw seed_top, potem według popularności malejąco
    def sort_key(r):
        pri = 0 if r.get("source") == "seed_top" else 1
        pop = r.get("popularity") or 0
        return (pri, -int(pop))
    rows = sorted(rows, key=sort_key)

    if len(rows) > TARGET_TRACKS:
        rows = rows[:TARGET_TRACKS]

    df = pd.DataFrame(rows, columns=["track_id","name","artist_id","artist_name","album","popularity","source"])
    meta = {
        "seeds": seed_artist_ids,
        "collected": len(rows),
        "per_artist_limit": TOP_PER_ARTIST,
        "related_per_seed": RELATED_PER_SEED,
        "market": MARKET,
    }
    return df, meta

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(PROC, exist_ok=True)
    sp = sp_user()

    profile = safe_read_json(f"{PROC}/profile.json")
    catalog = safe_read_csv(f"{PROC}/catalog.csv")
    saved   = safe_read_csv(f"{RAW}/saved_tracks.csv")

    # Seedy
    seeds_history = pick_top_artists_from_profile(profile, SEEDS_HISTORY_MAX)
    seeds_prefs   = pick_top_artists_from_saved(saved, SEEDS_PREFS_MAX)

    # fallback, gdyby saved puste
    if not seeds_prefs:
        seeds_prefs = seeds_history[:SEEDS_PREFS_MAX]

    print("=== HISTORY ===")
    hist_df, hist_meta = gen_for_seeds(sp, seeds_history, catalog)
    hist_df.to_csv(f"{PROC}/recs_history.csv", index=False, encoding="utf-8")
    print(f"→ data/processed/recs_history.csv   ({len(hist_df)} utworów)")

    print("=== PREFS ===")
    prefs_df, prefs_meta = gen_for_seeds(sp, seeds_prefs, catalog)
    prefs_df.to_csv(f"{PROC}/recs_prefs.csv", index=False, encoding="utf-8")
    print(f"→ data/processed/recs_prefs.csv     ({len(prefs_df)} utworów)")

    # Meta
    meta = {
        "seeds_history": {"artist_ids": seeds_history},
        "seeds_prefs": {"artist_ids": seeds_prefs},
        "params": {
            "SEEDS_HISTORY_MAX": SEEDS_HISTORY_MAX,
            "SEEDS_PREFS_MAX": SEEDS_PREFS_MAX,
            "RELATED_PER_SEED": RELATED_PER_SEED,
            "TOP_PER_ARTIST": TOP_PER_ARTIST,
            "TARGET_TRACKS": TARGET_TRACKS,
            "MARKET": MARKET,
        },
        "summary": {
            "history_tracks": len(hist_df),
            "prefs_tracks": len(prefs_df),
        }
    }
    with open(f"{PROC}/recs_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print("✅ Wygenerowano rekomendacje (Top Tracks + opcjonalnie Related).")
    print("→ data/processed/recs_history.csv")
    print("→ data/processed/recs_prefs.csv")
    print("→ data/processed/recs_meta.json")

if __name__ == "__main__":
    main()
