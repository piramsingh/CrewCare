# CrewCare

Exposure awareness for NYC transit workers. Platform conditions at all 496
subway stations — **PM2.5**, **temperature**, **humidity** and **mould risk** —
modelled from live outdoor readings, combined with what workers report from the
platform, and served to two audiences: a worker messaging portal and an
operations dashboard.

**Every platform figure is modelled, not measured.** No public per-station feed
exists for the NYC subway, so the numbers are physical estimates from live
street-level data. They are a planning prior for where to look first, never a
clearance that a station is safe. The worker reports shipped with the repo are
a synthetic corpus. Both are labelled as such wherever they appear on screen.

## Repository map

```
admin_dashboard/     the science: models + the data they read
  admin_dashboard_model/   PM2.5, heat, mould and the 1–5 risk level
  datasets/                station spine + the worker-report corpus
crewcare/            the product: React web app + its JSON API
  src/                     worker portal and operations dashboard
  server/                  FastAPI over the models above
project/             standalone WhatsApp linking service (not used by the web demo)
```

Each folder has its own README covering what lives there and why:
[`admin_dashboard/`](admin_dashboard/README.md) ·
[`admin_dashboard/datasets/`](admin_dashboard/datasets/README.md) ·
[`admin_dashboard/admin_dashboard_model/`](admin_dashboard/admin_dashboard_model/README.md) ·
[`crewcare/`](crewcare/README.md) ·
[`crewcare/server/`](crewcare/server/README.md) ·
[`project/`](project/README.md)

## How the parts fit

```
Open-Meteo (live, no key)
        │
        ▼
admin_dashboard/admin_dashboard_model/     ← physical models, pure Python
  openmeteo.py  → outdoor readings, 3 requests for the whole network
  indoor.py     → platform PM2.5 (train wheel and brake wear ÷ ventilation)
  thermal.py    → platform temperature, humidity, heat index
  flood.py      → rainfall exceedance and mould risk
  risk.py       → the 1–5 level, the maximum of three axes
  conditions.py → scores all 496 stations; the headless entry point
  complaints.py → the anonymous worker-report store
        │
        ▼
crewcare/server/ops/api.py                 ← JSON; adds no science
        │  /api/ops/snapshot · /api/ops/station/{id}
        ▼
crewcare/src/screens/admin/                ← the dashboard
```

The dashboard calculates no environmental value of its own. If the models
cannot load or Open-Meteo is unreachable, the API returns an error and the
dashboard says so — nothing is filled in with a plausible number.

## Quick start

Two processes: the API, then the web app.

```bash
# 1. the API  (http://localhost:8000)
cd crewcare/server
pip install -r requirements.txt
uvicorn main:app --port 8000

# 2. the web app  (http://localhost:5173)
cd crewcare
npm install
npm run dev
```

Sign in with any ID. `A0117` opens the operations dashboard, `W1042` the worker
portal.

The first snapshot scores all 496 stations and takes a few seconds; Open-Meteo
responses are then cached on disk for three hours.

### Without the web app

The models run on their own, and print the same figures the dashboard shows:

```bash
cd admin_dashboard/admin_dashboard_model
pip install -r requirements.txt

python conditions.py                 # top 5 highest health-risk stations
python conditions.py --json          # the same, as JSON
python test_conditions.py            # 22 checks against live data

streamlit run app.py                 # the original Streamlit dashboard
```

## Data

| source | what it gives | licence / access |
|---|---|---|
| [Open-Meteo](https://open-meteo.com) | live outdoor air quality, weather, rainfall, river discharge | free, no key, non-commercial |
| MTA Subway Stations + Entrances (NYS Open Data) | the 496-station spine: coordinates, routes, structure, ADA | public |
| `datasets/worker_complaints.csv` | 449 synthetic worker reports | generated here; **not real submissions** |

## Reading further

- [`admin_dashboard/admin_dashboard_model/METHODOLOGY.md`](admin_dashboard/admin_dashboard_model/METHODOLOGY.md)
  — every formula, constant and limitation behind the four figures.
- [`crewcare/README.md`](crewcare/README.md) — the product: conversation design,
  design system, what is real and what is simulated.
