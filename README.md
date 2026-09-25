# CrewCares

**Exposure awareness for NYC transit workers.** A worker gets a text before their
shift telling them what the air is like at their station, answers a private
health check-in that never leaves their phone, and can file a station complaint
that goes to their union rep.

![CrewCares demo — a worker gets a shift alert, answers a private health check-in, files a station complaint, and their union rep sees the pattern](docs/crewcares-demo.gif)

▶ **[Watch with sound (23 seconds)](docs/crewcares-demo.mp4)**

---

## What problem this solves

A transit worker shouldn't have to hand over their medical history to report a
hazard.

Today there is no per-station air quality feed for the NYC subway, and no easy
way for a worker to flag "the dust on this platform is bad" so that it becomes
their union's problem rather than their own. CrewCares does both, while keeping a
hard line between the two.

**Members keep their health. Their union gets what it needs to act.**

## How it works, in plain terms

The worker never installs anything. Everything happens in a text thread.

**1 · They get an alert before the shift**

> "Good morning. You're at 42nd Street today and the dust is running hotter than
> usual. Wear an N95 to stay protected."

Sent about 90 minutes before they report, based on where they're working that
day.

**2 · They answer a private check-in**

How they're feeling, a doctor's note if they want to add one, Apple Health if
they want to connect it — each data type granted one at a time. **All of it stays
on the phone.** None of it is aggregated and none of it reaches the dashboard.

**3 · They can file a complaint**

This is the one thing that deliberately leaves the phone. The confirmation says
so out loud:

> "Filed. Your local gets the station, the date and what you wrote. Nothing about
> your health goes with it."

**4 · Their union rep sees the pattern**

A dashboard showing where complaints cluster, which platforms the exposure model
flags, and where the two agree — so a rep can act on a station rather than an
anecdote. It never shows anyone's health answers, because it never receives them.

## What's real and what isn't

This is a prototype built at a hackathon, and it is labelled that way on every
screen. Being precise about this matters more than looking finished.

| | |
|---|---|
| **Real** | The privacy architecture. The physical models. Live outdoor weather and air quality from Open-Meteo. The 496-station spine from NYS Open Data. |
| **Modelled, not measured** | Every platform figure — PM2.5, temperature, humidity, mould risk. No public per-station feed exists, so these are physical estimates from live street-level data. They are a prior for **where to look first**, never a clearance that a station is safe. |
| **Simulated** | The worker reports. The 449 complaints shipped with the repo are a synthetic corpus, not real submissions. |
| **Not built** | Real authentication, a live messaging integration, and the Apple Health bridge (which needs a native iOS app). The demo simulates these end to end. |

Independent student project. **Not affiliated with the MTA.**

---

<!-- Everything below is for developers. -->

## Repository map

```
admin_dashboard/     the science: models + the data they read
  admin_dashboard_model/   PM2.5, heat, mould and the 1–5 risk level
  datasets/                station spine + the worker-report corpus
crewcare/            the product: React web app + its JSON API
  src/                     worker portal and operations dashboard
  server/                  FastAPI over the models above
project/             standalone WhatsApp linking service (not used by the web demo)
docs/                demo video, GIF and poster frame
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

> **If the dashboard shows an error**, the API could not find the models. They
> live in `admin_dashboard/admin_dashboard_model/`; point at them explicitly with
> `ADMIN_MODEL_DIR=/path/to/admin_dashboard_model uvicorn main:app --port 8000`.

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
