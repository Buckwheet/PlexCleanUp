import logging
import httpx
from app.config import RADARR_URL, RADARR_API_KEY, DRY_RUN

log = logging.getLogger("plexcleanup.radarr")


def _headers():
    return {"X-Api-Key": RADARR_API_KEY}


def _get_all_movies() -> list[dict]:
    r = httpx.get(f"{RADARR_URL}/api/v3/movie", headers=_headers(), timeout=60)
    r.raise_for_status()
    if not r.text or r.text[0] != '[':
        raise ValueError(f"Radarr returned unexpected response (check RADARR_URL): {r.text[:100]}")
    return r.json()


def build_lookup() -> dict:
    """Build lookup maps: tmdb_id -> radarr_id, imdb_id -> radarr_id."""
    movies = _get_all_movies()
    by_tmdb = {}
    by_imdb = {}
    for m in movies:
        rid = m["id"]
        if m.get("tmdbId"):
            by_tmdb[str(m["tmdbId"])] = rid
        if m.get("imdbId"):
            by_imdb[m["imdbId"]] = rid
    return {"tmdb": by_tmdb, "imdb": by_imdb}


def find_radarr_id(tmdb_id: str, imdb_id: str, lookup: dict) -> int | None:
    if tmdb_id and tmdb_id in lookup["tmdb"]:
        return lookup["tmdb"][tmdb_id]
    if imdb_id and imdb_id in lookup["imdb"]:
        return lookup["imdb"][imdb_id]
    return None


def delete_movie(radarr_id: int):
    """Delete movie from Radarr with file deletion and import exclusion."""
    if DRY_RUN:
        log.info(f"DRY RUN: Would delete Radarr movie id={radarr_id}")
        return
    r = httpx.delete(
        f"{RADARR_URL}/api/v3/movie/{radarr_id}",
        headers=_headers(),
        params={"deleteFiles": "true", "addImportExclusion": "true"},
        timeout=30,
    )
    r.raise_for_status()
