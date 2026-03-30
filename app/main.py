import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from app.config import PAGE_SIZE, GRACE_PERIOD_DAYS
from app.db import init_db, get_db
from app import plex_client, radarr_client
from app.scheduler import start_scheduler, run_scan, get_cached_candidates

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(a):
    init_db()
    start_scheduler()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


class RatingKeys(BaseModel):
    rating_keys: list[str]


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/candidates")
def candidates(page: int = Query(1, ge=1), page_size: int = Query(PAGE_SIZE, ge=1, le=50)):
    all_c = get_cached_candidates()
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "total": len(all_c),
        "page": page,
        "page_size": page_size,
        "items": all_c[start:end],
    }


@app.post("/api/mark")
def mark(body: RatingKeys):
    candidates = get_cached_candidates()
    lookup = {c["ratingKey"]: c for c in candidates}
    db = get_db()
    added = []
    for rk in body.rating_keys:
        c = lookup.get(rk)
        if not c:
            continue
        try:
            db.execute(
                "INSERT OR IGNORE INTO marked_items (plex_rating_key, title, year, file_size, tmdb_id, imdb_id) VALUES (?,?,?,?,?,?)",
                (rk, c["title"], c["year"], c["file_size"], c["tmdb_id"], c["imdb_id"]),
            )
            added.append(rk)
        except Exception:
            pass
    db.commit()
    db.close()
    if added:
        try:
            plex_client.add_to_collection(added)
        except Exception as e:
            logging.getLogger("plexcleanup").exception("Failed to add to collection")
    run_scan()  # refresh candidates
    return {"marked": len(added)}


@app.post("/api/delete-now")
def delete_now(body: RatingKeys):
    db = get_db()
    lookup = radarr_client.build_lookup()
    deleted = []

    # Check both candidates and marked items
    candidates = get_cached_candidates()
    clookup = {c["ratingKey"]: c for c in candidates}

    for rk in body.rating_keys:
        # Try candidates first, then marked items
        c = clookup.get(rk)
        if not c:
            row = db.execute("SELECT * FROM marked_items WHERE plex_rating_key=? AND status='pending'", (rk,)).fetchone()
            if row:
                c = {"ratingKey": rk, "title": row["title"], "year": row["year"],
                     "file_size": row["file_size"], "tmdb_id": row["tmdb_id"], "imdb_id": row["imdb_id"]}
        if not c:
            continue

        rid = radarr_client.find_radarr_id(c.get("tmdb_id", ""), c.get("imdb_id", ""), lookup)
        try:
            if rid:
                radarr_client.delete_movie(rid)
            db.execute("DELETE FROM marked_items WHERE plex_rating_key=?", (rk,))
            db.execute(
                "INSERT INTO deletion_log (title, year, file_size, method) VALUES (?,?,?,?)",
                (c["title"], c.get("year"), c.get("file_size", 0), "immediate"),
            )
            deleted.append(rk)
        except Exception:
            logging.getLogger("plexcleanup").exception(f"Failed to delete {c.get('title')}")

    db.commit()
    db.close()

    if deleted:
        try:
            plex_client.remove_from_collection(deleted)
        except Exception:
            pass

    run_scan()
    return {"deleted": len(deleted)}


@app.get("/api/marked")
def marked():
    db = get_db()
    rows = db.execute("SELECT * FROM marked_items WHERE status='pending' ORDER BY marked_at").fetchall()
    db.close()
    items = []
    for r in rows:
        marked_at = datetime.fromisoformat(r["marked_at"])
        expires_at = marked_at + timedelta(days=GRACE_PERIOD_DAYS)
        days_left = max(0, (expires_at - datetime.utcnow()).days)
        items.append({
            "plex_rating_key": r["plex_rating_key"],
            "title": r["title"],
            "year": r["year"],
            "file_size": r["file_size"],
            "marked_at": r["marked_at"],
            "days_left": days_left,
        })
    return {"items": items}


@app.get("/api/history")
def history():
    db = get_db()
    rows = db.execute("SELECT * FROM deletion_log ORDER BY deleted_at DESC LIMIT 100").fetchall()
    total_freed = db.execute("SELECT COALESCE(SUM(file_size),0) as total FROM deletion_log").fetchone()["total"]
    db.close()
    return {
        "total_freed": total_freed,
        "items": [dict(r) for r in rows],
    }


@app.get("/api/scan-state")
def scan_state():
    db = get_db()
    row = db.execute("SELECT * FROM scan_state WHERE id=1").fetchone()
    db.close()
    return dict(row) if row else {}


@app.post("/api/scan-now")
def scan_now():
    run_scan()
    return {"status": "scan_complete"}


@app.get("/")
def index():
    return FileResponse("static/index.html")
