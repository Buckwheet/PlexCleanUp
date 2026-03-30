# PlexCleanUp

A Dockerized tool that identifies unwatched movies on your Plex server and coordinates with Radarr to clean them up — Netflix style.

## How It Works

1. **Scans** your Plex movie library for titles added 90+ days ago with zero plays by any user
2. **Shows** you 10-15 candidates at a time in a web dashboard
3. **Mark for removal** — adds the movie to a "Leaving Plex Soon" Plex collection visible to all users, deletes after 14 days
4. **Delete now** — immediately removes from Radarr (files + import exclusion) so it won't be re-downloaded

## Quick Start

```bash
git clone https://github.com/Buckwheet/PlexCleanUp.git
cd PlexCleanUp
cp docker-compose.yml docker-compose.override.yml
# Edit docker-compose.override.yml with your actual values
docker compose up -d
```

Open `http://your-server:8141` in your browser.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PLEX_URL` | `http://localhost:32400` | Plex server URL |
| `PLEX_TOKEN` | | Your Plex authentication token |
| `RADARR_URL` | `http://localhost:7878` | Radarr URL |
| `RADARR_API_KEY` | | Radarr API key |
| `PRUNE_DAYS` | `90` | Days since added before a movie becomes a candidate |
| `GRACE_PERIOD_DAYS` | `14` | Days between marking and automatic deletion |
| `SCAN_INTERVAL_HOURS` | `24` | How often to scan for new candidates |
| `PAGE_SIZE` | `15` | Number of candidates shown per page |

## Unraid Setup

1. In the Docker tab, click "Add Container"
2. Set the repository to build from this repo, or build the image and push to your registry
3. Add the environment variables above with your Plex/Radarr details
4. Map port `8141` and add a volume for `/app/data` to persist the database

## Finding Your Plex Token

See: https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/

## Finding Your Radarr API Key

Settings → General → API Key in the Radarr web UI.
