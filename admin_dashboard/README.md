# admin_dashboard

The science behind the product: the models that estimate platform conditions,
and the data they read. Nothing in here imports anything from `crewcare/` — the
dependency runs one way, so the models can be used by a dashboard, a bot, a
notebook or a cron job without dragging a web app along.

```
admin_dashboard/
  admin_dashboard_model/   the models, the risk scale, the report store
  datasets/                the station spine and the worker-report corpus
```

## Why the two folders sit together

Every model resolves its data as `APP_DIR.parent / "datasets"` — that is, as a
sibling of `admin_dashboard_model/`. **Move one, move both**, or the spine and
the report corpus stop resolving. That single relative path is why the pair was
nested under `admin_dashboard/` as a unit rather than being scattered.

## What the models produce

Four figures per station, plus a level that combines them.

| figure | module | how |
|---|---|---|
| Platform PM2.5 | `indoor.py` | street reading **plus** what wheel and brake wear generate, divided by the ventilation rate |
| Platform temperature | `thermal.py` | heat balance: braking, equipment and people against ventilation and ground conduction |
| Humidity / heat index | `thermal.py` | dew point carried down from the street, relative humidity derived at platform temperature |
| Flood and mould risk | `flood.py` | hourly rainfall against NYC DEP sewer capacity, then EPA/ASHRAE humidity and drying-window thresholds |
| **Risk level 1–5** | `risk.py` | the **maximum** of three axes — particulates, heat, mould — never their average |

The level is a maximum on purpose: a station that is fine on heat and severe on
particulates is not "moderate", it is severe, and which axis drove it is what
tells you what to do about it. `risk.py` reports that axis as the `driver`.

Level 5 is reserved for acute conditions met on the shift; mould caps at 4
because it develops over days. Today's network runs 1–4, but a consumer should
handle all five — 5 becomes reachable when PM2.5 crosses 150 µg/m³ or the heat
index crosses 125 °F.

## Files

| file | contents |
|---|---|
| `conditions.py` | **the headless entry point.** Scores all 496 stations, ranks them, exports JSON. No Streamlit. |
| `risk.py` | the 1–5 scale, its thresholds, and the per-worker overlay (`WorkerProfile`, precautions) |
| `indoor.py` | platform PM2.5 source model |
| `thermal.py` | heat balance and psychrometrics |
| `flood.py` | pluvial exceedance and the mould verdict |
| `openmeteo.py` | live outdoor readings: grid dedupe, batched fetch, disk cache, metric registry |
| `complaints.py` | the anonymous worker-report store, the synthetic corpus and its aggregates |
| `charts.py` | Altair builders and palettes, used by the Streamlit app |
| `app.py` | the original Streamlit dashboard — a working reference for what each number means |
| `test_conditions.py` | 22 checks, run with plain `python` |
| `METHODOLOGY.md` | every formula, constant and limitation |

## Using it

```bash
cd admin_dashboard/admin_dashboard_model
pip install -r requirements.txt

python conditions.py                      # top 5 highest health-risk stations
python conditions.py --json --limit 10    # as JSON, ten of them
python conditions.py --borough Brooklyn   # scoped to one borough
python conditions.py --export risk.json   # write it for a non-Python consumer
python conditions.py --ttl-hours 0        # force a live fetch, ignore the cache

python test_conditions.py                 # verify the pipeline end to end
streamlit run app.py                      # the Streamlit dashboard
```

From Python:

```python
from conditions import score_stations, top_health_risk

top_health_risk(limit=5)          # ranked list of dicts, ready to render
score_stations()                  # one row per station, as a DataFrame
```

## Cost and caching

One refresh is **three HTTP requests for the entire network**, about four
seconds for all 496 stations. Responses cache to `.cache/` (gitignored) for
three hours by default:

- `ttl_hours=1.0` behind a web front end — matches Open-Meteo's hourly cadence
  and caps traffic no matter how many people load the page.
- `ttl_hours=0` forces a live fetch; use it for a scheduled export, not per
  page view.

The models need outbound network access and a writable `.cache/` directory.

## Honesty rules this code keeps

- **A missing value stays missing.** No model substitutes a plausible number
  when a reading is absent; it returns `None` and the caller renders "no data".
- **Modelled is not measured.** The platform figures apply assumed emission
  factors, a standard platform volume and a ventilation rate inferred from
  `structure`. Outdoor air quality resolves to a ~11 km grid.
- **The reports are synthetic** and carry a `demo` flag.
- The level saturates: dozens of enclosed stations share the top level because
  the PM2.5 source term is identical at equal service levels. Anything showing
  a "top N" should say how many are tied — `conditions.risk_list()` returns
  `tied_at_top` for exactly that.
