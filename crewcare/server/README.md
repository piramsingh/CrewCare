# crewcare/server

The seam between the React dashboard and the Python models. FastAPI, read-only,
and it adds no science: it calls `conditions.score_stations()` — the same
function the Streamlit app uses — and reshapes the result for the browser.

```
server/
  main.py              the FastAPI app and CORS
  ops/api.py           the endpoints
  ops/model_bridge.py  finds and imports the models
  requirements.txt     fastapi, uvicorn, pandas, requests
```

## Running it

```bash
cd crewcare/server
pip install -r requirements.txt
uvicorn main:app --port 8000
```

The first request scores all 496 stations and takes a few seconds. Open-Meteo
responses are cached on disk for three hours, so later requests are instant.
Python changes need a restart (`--reload` if you prefer).

## Endpoints

| route | returns |
|---|---|
| `GET /` | `{"status": "ok"}` |
| `GET /api/ops/snapshot?range=30 Days&ttl_hours=3` | everything the Overview needs, in one request |
| `GET /api/ops/station/{gtfs_stop_id}?range=30 Days` | that station's worker reports, newest first |

One snapshot call rather than one per panel, because the models compute the
whole network at once anyway; splitting it would re-score 496 stations per
panel.

`range` accepts `Live`, `Today`, `7 Days`, `30 Days`, `60 Days`. It filters
**worker reports only** — environmental readings are always current, never
re-cut by the window.

### What the snapshot carries

```jsonc
{
  "generatedAt": "2026-09-20T11:18:00-04:00",
  "kpis": { "stationsMonitored": 496, "highRiskPlatforms": 46,
            "workerReports": 233, "bothSignals": 87 },
  "stations": [ { "id": "L06", "name": "1 Av", "routes": ["L"],
                  "level": 3, "levelName": "Elevated", "driver": "Particulates",
                  "pm25": 42.0, "tempF": 80.5, "feelsF": 81.4,
                  "humidity": 51, "mould": "Low", "reports": 1,
                  "lat": 40.73, "lon": -73.98, "…": "…" } ],
  "concerns":        [ { "label": "Heat", "count": 69, "percent": 30 } ],
  "exposureByLine":  { "networkMedian": 42.0,
                       "lines": [ { "line": "E", "ratio": 2.14, "stations": 22 } ] },
  "recommendations": [ { "id": "both-signals", "title": "…", "detail": "…" } ],
  "reportsAreDemo": true,
  "provenance": { "outdoor": "live", "platform": "modelled",
                  "risk": "derived", "reports": "demo" }
}
```

`exposureByLine` is median platform PM2.5 per route as a multiple of the
network median — a **concentration**, not a worker's tour dose. Tour exposure
would need a roster and tour lengths, which this repo does not have.

`recommendations` are query results phrased as actions, computed here from the
same snapshot the screen renders. Nothing is generated prose, so the card
cannot assert something the data does not show.

## Two rules the endpoints keep

1. **Nothing is invented.** A metric the models cannot produce comes back
   `null` and the UI renders "No data available". If Open-Meteo is unreachable
   the endpoint returns 503 rather than a plausible number.
2. **Provenance travels with the data**, so the interface can be honest about
   what it is showing without the front end having to guess.

## The model bridge

`ops/model_bridge.py` puts `admin_dashboard/admin_dashboard_model/` on the path
and imports `conditions`, `risk`, `flood`, `openmeteo` and `complaints`
unchanged.

**The models live outside this folder.** `crewcare/` is not self-contained: the
bridge walks up to the repo root and looks for

```
<repo>/admin_dashboard/admin_dashboard_model/     ← current layout
<repo>/admin_dashboard_model/                     ← the older one
```

If neither exists, every `/api/ops/*` route returns 503 with the paths it
tried, and the dashboard shows "Data unavailable". To run this folder somewhere
else, point it at the models explicitly:

```bash
ADMIN_MODEL_DIR=/path/to/admin_dashboard_model uvicorn main:app --port 8000
```

The models in turn need their own `datasets/` sibling, so copy the pair.

## CORS

Any `localhost` port is allowed in development, because Vite picks whatever
port is free and pinning a list only produces confusing failures later. For a
deployment set `WEB_ORIGINS` to the exact origins — "any localhost" is not a
rule to leave in front of something reachable.
