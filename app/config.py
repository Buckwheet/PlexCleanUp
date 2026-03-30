import os

PLEX_URL = os.getenv("PLEX_URL", "http://localhost:32400").rstrip("/")
PLEX_TOKEN = os.getenv("PLEX_TOKEN", "")
RADARR_URL = os.getenv("RADARR_URL", "http://localhost:7878").rstrip("/")
RADARR_API_KEY = os.getenv("RADARR_API_KEY", "")
PRUNE_DAYS = int(os.getenv("PRUNE_DAYS", "90"))
GRACE_PERIOD_DAYS = int(os.getenv("GRACE_PERIOD_DAYS", "14"))
SCAN_INTERVAL_HOURS = int(os.getenv("SCAN_INTERVAL_HOURS", "24"))
PAGE_SIZE = int(os.getenv("PAGE_SIZE", "15"))
DB_PATH = os.getenv("DB_PATH", "/app/data/plexcleanup.db")

# Safety limits
MAX_DELETE_PER_REQUEST = int(os.getenv("MAX_DELETE_PER_REQUEST", "5"))
MAX_MARK_PER_REQUEST = int(os.getenv("MAX_MARK_PER_REQUEST", "15"))
DAILY_DELETE_LIMIT = int(os.getenv("DAILY_DELETE_LIMIT", "25"))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")
