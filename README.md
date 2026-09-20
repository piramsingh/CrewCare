# NYC Subway Station Conditions

A Streamlit dashboard showing modelled conditions on the platform of any of the
496 NYC subway stations: **PM2.5**, **temperature** and **humidity**.

```bash
pip install -r admin_dashboard_model/requirements.txt
streamlit run admin_dashboard_model/app.py
```

No API key required — outdoor readings come from
[Open-Meteo](https://open-meteo.com)'s free non-commercial tier.

## What it does

Live outdoor readings are transformed into platform estimates by three physical
models. Each station's ventilation and service level come from its own
`structure` and `route_count` in `datasets/nyc_subway_station_spine.csv`.

| figure | model |
|---|---|
| PM2.5 | street level **plus** what wheel and brake wear generate underground |
| temperature | heat balance — braking, equipment and people against ventilation and ground conduction |
| humidity | dew point conserved from the street, relative humidity derived at platform temperature |

**The platform figures are modelled estimates, not measurements.** No public
per-station feed exists for the NYC subway. See
[`admin_dashboard_model/METHODOLOGY.md`](admin_dashboard_model/METHODOLOGY.md) for
every formula, constant and limitation.

## Layout

| path | contents |
|---|---|
| `admin_dashboard_model/app.py` | the dashboard |
| `admin_dashboard_model/conditions.py` | station scoring and the top-5 highest health-risk list, without Streamlit — importable, or `--export` to JSON |
| `admin_dashboard_model/test_conditions.py` | checks for the above, including parity with the dashboard's own scoring |
| `admin_dashboard_model/openmeteo.py` | live outdoor readings, grid dedupe, disk cache |
| `admin_dashboard_model/indoor.py` | PM2.5 source model |
| `admin_dashboard_model/thermal.py` | heat balance and psychrometrics |
| `admin_dashboard_model/charts.py` | Altair builders and palette |
| `admin_dashboard_model/risk.py` | the 1–5 level, its thresholds and the worker overlay |
| `admin_dashboard_model/complaints.py` | anonymous worker reports, the demo corpus and its aggregates |
| `admin_dashboard_model/METHODOLOGY.md` | how all three figures are calculated |
| `datasets/worker_complaints.csv` | the published synthetic report corpus, 449 records; `days_ago` is re-anchored to today on load |
| `datasets/nyc_subway_station_spine.csv` | 496 stations, built from MTA Subway Stations (`39hk-dx4f`) and Entrances (`i9wp-a4ja`) on NYS Open Data |

## Cost

One refresh is **three HTTP requests for the entire system** — stations are
deduplicated to the weather models' grid cells before fetching — cached to disk
for 3 hours. About 24 requests a day.
