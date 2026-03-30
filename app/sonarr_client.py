import logging
import httpx
from app.config import SONARR_URL, SONARR_API_KEY, DRY_RUN

log = logging.getLogger("plexcleanup.sonarr")


def _headers():
    return {"X-Api-Key": SONARR_API_KEY}


def _get_all_series() -> list[dict]:
    r = httpx.get(f"{SONARR_URL}/api/v3/series", headers=_headers(), timeout=60)
    r.raise_for_status()
    if not r.text or r.text[0] != '[':
        raise ValueError(f"Sonarr returned unexpected response: {r.text[:100]}")
    return r.json()


def build_lookup() -> dict:
    """Build lookup maps: tvdb_id -> sonarr_id, imdb_id -> sonarr_id."""
    series = _get_all_series()
    by_tvdb = {}
    by_imdb = {}
    for s in series:
        sid = s["id"]
        if s.get("tvdbId"):
            by_tvdb[str(s["tvdbId"])] = sid
        if s.get("imdbId"):
            by_imdb[s["imdbId"]] = sid
    return {"tvdb": by_tvdb, "imdb": by_imdb}


def find_sonarr_id(tvdb_id: str, imdb_id: str, lookup: dict) -> int | None:
    if tvdb_id and tvdb_id in lookup["tvdb"]:
        return lookup["tvdb"][tvdb_id]
    if imdb_id and imdb_id in lookup["imdb"]:
        return lookup["imdb"][imdb_id]
    return None


def delete_series(sonarr_id: int):
    """Delete series from Sonarr with file deletion and import exclusion."""
    if DRY_RUN:
        log.info(f"DRY RUN: Would delete Sonarr series id={sonarr_id}")
        return
    r = httpx.delete(
        f"{SONARR_URL}/api/v3/series/{sonarr_id}",
        headers=_headers(),
        params={"deleteFiles": "true", "addImportListExclusion": "true"},
        timeout=30,
    )
    r.raise_for_status()
