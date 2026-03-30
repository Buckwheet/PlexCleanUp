import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from app.config import GRACE_PERIOD_DAYS, SCAN_INTERVAL_HOURS
from app.db import get_db
from app import radarr_client, plex_client

log = logging.getLogger("plexcleanup.scheduler")
scheduler = BackgroundScheduler()
_cached_candidates: list[dict] = []


def get_cached_candidates() -> list[dict]:
    return _cached_candidates


def run_scan():
    global _cached_candidates
    log.info("Running candidate scan...")
    try:
        db = get_db()
        marked_keys = {r["plex_rating_key"] for r in db.execute(
            "SELECT plex_rating_key FROM marked_items WHERE status='pending'"
        ).fetchall()}
        db.close()

        all_candidates = plex_client.get_candidates()
        _cached_candidates = [c for c in all_candidates if c["ratingKey"] not in marked_keys]

        db = get_db()
        db.execute("UPDATE scan_state SET last_scan_at=?, next_scan_at=? WHERE id=1", (
            datetime.utcnow().isoformat(),
            (datetime.utcnow() + timedelta(hours=SCAN_INTERVAL_HOURS)).isoformat(),
        ))
        db.commit()
        db.close()
        log.info(f"Scan complete. {len(_cached_candidates)} candidates found.")
    except Exception:
        log.exception("Scan failed")


def run_cleanup():
    log.info("Running scheduled cleanup...")
    try:
        db = get_db()
        cutoff = (datetime.utcnow() - timedelta(days=GRACE_PERIOD_DAYS)).isoformat()
        expired = db.execute(
            "SELECT * FROM marked_items WHERE status='pending' AND marked_at <= ?", (cutoff,)
        ).fetchall()

        if not expired:
            log.info("No expired items to clean up.")
            db.close()
            return

        lookup = radarr_client.build_lookup()
        deleted_keys = []

        for item in expired:
            rid = radarr_client.find_radarr_id(item["tmdb_id"], item["imdb_id"], lookup)
            try:
                if rid:
                    radarr_client.delete_movie(rid)
                db.execute("UPDATE marked_items SET status='deleted' WHERE id=?", (item["id"],))
                db.execute(
                    "INSERT INTO deletion_log (title, year, file_size, method) VALUES (?,?,?,?)",
                    (item["title"], item["year"], item["file_size"], "scheduled"),
                )
                deleted_keys.append(item["plex_rating_key"])
                log.info(f"Deleted: {item['title']} ({item['year']})")
            except Exception:
                log.exception(f"Failed to delete {item['title']}")

        db.commit()
        db.close()

        if deleted_keys:
            try:
                plex_client.remove_from_collection(deleted_keys)
            except Exception:
                log.exception("Failed to remove items from collection")

        run_scan()  # refresh candidates
    except Exception:
        log.exception("Cleanup failed")


def start_scheduler():
    scheduler.add_job(run_scan, "interval", hours=SCAN_INTERVAL_HOURS, id="scan", replace_existing=True)
    scheduler.add_job(run_cleanup, "interval", hours=1, id="cleanup", replace_existing=True)
    scheduler.start()
    run_scan()  # initial scan on startup
