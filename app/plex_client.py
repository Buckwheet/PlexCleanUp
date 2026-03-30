import httpx
import time
import xml.etree.ElementTree as ET
from app.config import PLEX_URL, PLEX_TOKEN, PRUNE_DAYS


def _headers():
    return {"X-Plex-Token": PLEX_TOKEN, "Accept": "application/xml"}


def _get(path: str, params: dict = None) -> ET.Element:
    r = httpx.get(f"{PLEX_URL}{path}", headers=_headers(), params=params or {}, timeout=60)
    r.raise_for_status()
    return ET.fromstring(r.text)


def get_movie_library_id() -> str | None:
    """Find the first movie library section ID."""
    root = _get("/library/sections")
    for d in root.findall("Directory"):
        if d.get("type") == "movie":
            return d.get("key")
    return None


def get_all_movies(library_id: str) -> list[dict]:
    """Fetch all movies with GUIDs from a library section."""
    root = _get(f"/library/sections/{library_id}/all", {"includeGuids": "1"})
    movies = []
    for v in root.findall("Video"):
        tmdb_id = imdb_id = ""

        # New-style Guid child elements: <Guid id="tmdb://12345"/>
        for g in v.findall("Guid"):
            gid = g.get("id", "")
            if gid.startswith("tmdb://"):
                tmdb_id = gid.replace("tmdb://", "")
            elif gid.startswith("imdb://"):
                imdb_id = gid.replace("imdb://", "")

        # Legacy guid attribute: com.plexapp.agents.imdb://tt0075314?lang=en
        if not tmdb_id and not imdb_id:
            legacy = v.get("guid", "")
            if "imdb://" in legacy:
                imdb_id = legacy.split("imdb://")[1].split("?")[0]
            elif "themoviedb://" in legacy:
                tmdb_id = legacy.split("themoviedb://")[1].split("?")[0]

        file_size = 0
        for media in v.findall("Media"):
            for part in media.findall("Part"):
                file_size += int(part.get("size", 0))

        movies.append({
            "ratingKey": v.get("ratingKey"),
            "title": v.get("title", ""),
            "year": int(v.get("year", 0)),
            "addedAt": int(v.get("addedAt", 0)),
            "viewCount": int(v.get("viewCount", 0)),
            "file_size": file_size,
            "tmdb_id": tmdb_id,
            "imdb_id": imdb_id,
        })
    return movies


def get_play_history() -> set[str]:
    """Return set of ratingKeys that have any play history across all users."""
    played = set()
    root = _get("/status/sessions/history/all")
    for v in root.findall("Video"):
        rk = v.get("ratingKey")
        if rk:
            played.add(rk)
    return played


def get_candidates() -> list[dict]:
    """Get movies added 90+ days ago with zero plays by any user."""
    lib_id = get_movie_library_id()
    if not lib_id:
        return []
    movies = get_all_movies(lib_id)
    played = get_play_history()
    cutoff = int(time.time()) - (PRUNE_DAYS * 86400)
    candidates = []
    for m in movies:
        if m["addedAt"] < cutoff and m["viewCount"] == 0 and m["ratingKey"] not in played:
            candidates.append(m)
    candidates.sort(key=lambda x: x["file_size"], reverse=True)
    return candidates


# --- Collection management ---

def _find_collection(library_id: str, name: str) -> str | None:
    """Find a collection by name, return its ratingKey."""
    root = _get(f"/library/sections/{library_id}/collections")
    for d in root.findall("Directory"):
        if d.get("title") == name:
            return d.get("ratingKey")
    return None


def _ensure_collection(library_id: str, name: str) -> str:
    """Get or create the collection, return its ratingKey."""
    key = _find_collection(library_id, name)
    if key:
        return key
    # Create by adding a dummy then we'll manage items directly
    # Plex creates collections via the machine ID endpoint
    r = httpx.post(
        f"{PLEX_URL}/library/collections",
        headers=_headers(),
        params={
            "type": "1",  # movie
            "title": name,
            "sectionId": library_id,
            "smart": "0",
        },
        timeout=30,
    )
    r.raise_for_status()
    root = ET.fromstring(r.text)
    return root.find("Directory").get("ratingKey")


def add_to_collection(rating_keys: list[str]):
    """Add movies to the 'Leaving Plex Soon' collection."""
    lib_id = get_movie_library_id()
    if not lib_id:
        return
    col_key = _ensure_collection(lib_id, "! Leaving Plex Soon")
    machine_id = _get("/").get("machineIdentifier", "")
    for rk in rating_keys:
        httpx.put(
            f"{PLEX_URL}/library/collections/{col_key}/items",
            headers=_headers(),
            params={"uri": f"server://{machine_id}/com.plexapp.plugins.library/library/metadata/{rk}"},
            timeout=30,
        )


def get_movie_file_path(rating_key: str) -> str | None:
    """Get the file path for a movie by its ratingKey."""
    root = _get(f"/library/metadata/{rating_key}")
    for v in root.findall("Video"):
        for media in v.findall("Media"):
            for part in media.findall("Part"):
                f = part.get("file")
                if f:
                    # Return the parent directory of the file
                    return f.rsplit("/", 1)[0] if "/" in f else f.rsplit("\\", 1)[0]
    return None


def scan_library(path: str = None):
    """Trigger a Plex library scan. If path is given, only scan that folder."""
    lib_id = get_movie_library_id()
    if not lib_id:
        return
    params = {}
    if path:
        params["path"] = path
    httpx.get(f"{PLEX_URL}/library/sections/{lib_id}/refresh", headers=_headers(), params=params, timeout=30)
    httpx.put(f"{PLEX_URL}/library/sections/{lib_id}/emptyTrash", headers=_headers(), timeout=30)


def remove_from_collection(rating_keys: list[str]):
    """Remove movies from the 'Leaving Plex Soon' collection."""
    lib_id = get_movie_library_id()
    if not lib_id:
        return
    col_key = _find_collection(lib_id, "! Leaving Plex Soon")
    if not col_key:
        return
    for rk in rating_keys:
        httpx.delete(
            f"{PLEX_URL}/library/collections/{col_key}/items/{rk}",
            headers=_headers(),
            timeout=30,
        )
