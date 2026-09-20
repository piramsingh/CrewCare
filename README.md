# NYC Subway Station Conditions

A Streamlit dashboard showing modelled conditions on the platform of any of the
496 NYC subway stations: **PM2.5**, **temperature** and **humidity**.

```bash
pip install -r station_air_quality/requirements.txt
streamlit run station_air_quality/app.py
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
[`station_air_quality/METHODOLOGY.md`](station_air_quality/METHODOLOGY.md) for
every formula, constant and limitation.

## Layout

| path | contents |
|---|---|
| `station_air_quality/app.py` | the dashboard |
| `station_air_quality/openmeteo.py` | live outdoor readings, grid dedupe, disk cache |
| `station_air_quality/indoor.py` | PM2.5 source model |
| `station_air_quality/thermal.py` | heat balance and psychrometrics |
| `station_air_quality/charts.py` | Altair builders and palette |
| `station_air_quality/METHODOLOGY.md` | how all three figures are calculated |
| `datasets/nyc_subway_station_spine.csv` | 496 stations, built from MTA Subway Stations (`39hk-dx4f`) and Entrances (`i9wp-a4ja`) on NYS Open Data |

## Cost

One refresh is **three HTTP requests for the entire system** — stations are
deduplicated to the weather models' grid cells before fetching — cached to disk
for 3 hours. About 24 requests a day.
