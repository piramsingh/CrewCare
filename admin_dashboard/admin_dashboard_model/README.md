# NYC Subway Station Air Quality

Real-time air quality at any of the 496 NYC subway stations, from
[Open-Meteo](https://open-meteo.com/en/docs/air-quality-api), joined to
`admin_dashboard/datasets/nyc_subway_station_spine.csv`.

```bash
.venv/bin/python -m streamlit run admin_dashboard/admin_dashboard_model/app.py
```

No API key. Open-Meteo's free tier needs none for non-commercial use.

## What you get

Pick a station and the app shows, for its location:


The dashboard shows four things for the selected station: **where it is**, and
the three modelled platform figures — **PM2.5**, **temperature** and
**humidity** — each with the street reading it was derived from.

The models below compute those three. `openmeteo.py` supplies the live outdoor
readings they start from, and carries more metrics than the dashboard displays
(ozone, NO₂, CO, SO₂, dew point, pressure, wind, UV) if you want to surface
more.

## The platform PM2.5 estimate

The **Underground** tab estimates platform PM2.5 from a mechanical source
balance. Trains generate iron-rich particles through wheel-rail wear and brake
abrasion; that mass enters a fixed platform volume which ventilation clears at
a finite rate:

```
S_train = n × [ w × m_w × t_cruise  +  b × m_b × t_brake ]
ΔC      = S_train / (V × ACH)
C_in    = C_out + ΔC
```

`ΔC` is the concentration the station's own machinery sustains **above** street
level. It does not depend on `C_out`, so it acts as a constant offset: platform
air tracks the street's shape but sits far above its level.

**The tab has no controls.** Every coefficient is a module constant in
`indoor.py`, identical at every station, so two stations differ only through
what the spine actually records about them.

| term | value | source |
|---|---|---|
| `w`, `b` | 80 wheels, 80 brake pads | constant (10-car R160/R211) |
| `m_w`, `m_b` | 40, 36 µg/s each | constant |
| `t_cruise`, `t_brake` | 40 s, 15 s | constant |
| `V` | 160 × 15 × 5 m = 12,000 m³ | constant |
| `n` | `route_count` × 9 /h | `route_count` from the spine; the 9 is **assumed** |
| `ACH` | by enclosure class | **from the spine** |
| `C_out` | live PM2.5 | Open-Meteo |

### What the spine drives

`structure` resolves the enclosure class, which sets `ACH`:

| `structure` | stations | enclosure | ACH |
|---|---|---|---|
| `Subway` | 283 | enclosed box below grade | 4.0 |
| `Open Cut` | 39 | trench open to the sky | 12.0 |
| `Elevated`, `Viaduct`, `At Grade`, `Embankment` | 174 | open air | — (ΔC = 0) |

`route_count` sets service level at a constant **9 trains/h per route**, both
directions — about one train every 13 minutes each way. That rate is an
assumption, not data: the spine carries no frequency, headway or schedule
field, so the model cannot tell rush hour from a Sunday. Real per-stop
frequencies would have to come from MTA GTFS `stop_times.txt`.

Enclosure class and route count together fix ΔC, so all 496 stations collapse
onto seven values:

| enclosure | stations | ΔC range (µg/m³) |
|---|---|---|
| Enclosed box below grade | 283 | 32.1 – 128.4 |
| Trench open to the sky | 39 | 10.7 – 32.1 |
| Open air | 174 | 0 |

Open-air stations return ΔC = 0 by construction: with no roof there is no
volume for dust to accumulate in, so the platform estimate is just the street
reading.

**PM10 is not modelled.** The infiltration model that previously drove it is
still in `indoor.py` and still correct for outdoor-origin pollutants, just not
surfaced in the UI.

### What this model assumes

- **The spine records no station depth.** Every underground station carries the
  single value `Subway`, so all 283 take the same system-average 4.0 ACH. The
  plausible proxies do not work — 191 St, among the deepest in the system,
  lists 2 entrances while shallow Bergen St lists 6, and
  `platform_to_street_m` is a horizontal offset, not a depth. A deep rock-bored
  station really does trap air far more than a shallow cut-and-cover box, and
  this model cannot see that difference.
- **The three enclosure classes are mine, not the dataset's.** The spine's
  `structure` column supplies six raw values; collapsing them into
  enclosed/trench/open-air, and the ACH numbers attached to each, are
  judgments. The spine also ships its own `structure_group`, which this model
  does **not** use — it groups `Embankment` with `Open Cut`, whereas a raised
  earth embankment is open air for ventilation purposes, not a trench. That
  affects 6 stations.
- **12.0 ACH for an open cut is a judgment**, not a measurement. The dataset
  says the trench is roofless; nothing in it quantifies the exchange rate.
- **Removal is by airflow only.** A fuller balance would also drain the source
  through deposition, `S/(V·(ACH + k))`, putting ΔC somewhat lower.
- **Uniform well-mixed air, constant ventilation, flat service.** Real platforms
  have strong trackbed-to-mezzanine gradients, the piston effect is pulsed by
  train arrivals, and service varies peak to off-peak.

## The platform heat and humidity estimate

The **Heat & humidity** tab estimates platform temperature and humidity, in
`thermal.py`. Same skeleton as the PM2.5 model — a source over a ventilation
rate — with two differences that matter.

### Temperature: heat has a second sink

```
T_in = (Q_internal + C_vent·T_out + UA·T_ground) / (C_vent + UA)
```

| term | value |
|---|---|
| `Q_brake` | `n · ½mv² · f_local / 3600`, m = 400 t, v = 50 km/h, f_local = 0.70 |
| `Q_ac` | `n · 250 kW · 40 s / 3600` — car A/C rejects heat during the dwell |
| `Q_people`, `Q_equip` | 150 × 100 W, 30 kW |
| `C_vent` | `ρ·c_p·V·ACH/3600` = 16.1 kW/K at 4 ACH |
| `UA` | `U_g · A_shell`, `U_g` = 1.5 W/(m²K), all six faces of the box |
| `T_ground` | **21.5 °C, calibrated** — solved so the quietest enclosed
station reads 55 °F in the coldest weather (see below) |

Unlike dust, heat also conducts into the tunnel shell and surrounding earth.
That `UA` term compresses the seasonal swing: platforms run far above the
street in winter and only a little above it in summer.

**`T_ground` is calibrated, not assumed.** Virgin earth at depth would sit near
13 °C (NYC's annual mean), but the tunnels have been shedding heat into the
surrounding ground for over a century, so a station touches much warmer earth
than that. Rather than guess, `thermal.py` inverts the heat balance against a
single anchor — the quietest enclosed station (1 route, 9 trains/h) reads
**55 °F in the coldest weather** — and solves for the ground temperature that
produces it. The answer is **21.5 °C**, independently consistent with a
century-heated tunnel surround. Changing any other constant re-solves the
anchor automatically.

Resulting platform temperatures:

| street | 1 route | 2 routes | 3 routes | 4 routes |
|---|---|---|---|---|
| 30 °F | **55.0** | 61.4 | 67.9 | 74.3 |
| 50 °F | 67.4 | 73.8 | 80.3 | 86.7 |
| 70 °F | 79.8 | 86.3 | 92.7 | 99.1 |
| 88 °F | 91.0 | 97.4 | 103.9 | 110.3 |

Note the platform still swings 36 °F across the year while the street swings
58 °F. That ratio is fixed by `C_vent/(C_vent + UA)` = 0.62 and is *not*
affected by `T_ground`, which shifts the whole curve without compressing it.
If real platforms hold a narrower band than this, the fix is a larger `UA`
relative to `C_vent`, not a different ground temperature.

**The steady-state assumption needs care here.** PM2.5 re-equilibrates in
~15 min (`1/ACH`), so a steady-state formula on hourly data is fine. The tunnel
shell has a time constant of **~6 days**, so the balance is driven by an
exponentially weighted trailing mean of *daily* outdoor temperature, not the
current hour. That is what the third API request is for.

### Humidity: never model RH directly

Relative humidity is a ratio against a saturation capacity that moves with
temperature, so heating air changes its RH without adding or removing any
water. The chain therefore runs through absolute moisture:

```
e_sat(T) = 6.112 · exp(17.67·T / (T + 243.5))        [hPa, °C]
e_out    = e_sat(T_dew)                               ← dew_point_2m, preferred
w        = 621.97 · e / (p − e)                       [g water / kg dry air]
w_in     = w_out + Ṡ_water / ṁ_air,  ṁ_air = ρ·V·ACH/3600
e_in     = min( w_in·p / (621.97 + w_in),  e_sat(T_in) )   ← saturation cap
RH_in    = 100 · e_in / e_sat(T_in)
```

`Ṡ_water` = 12 g/s seepage + 150 passengers × 50 g/h. The saturation cap is not
optional — without it the model emits RH > 100% in winter.

A platform typically reads **lower** RH than the street while holding **more**
water, at a higher dew point. Dew point and heat index are reported alongside
RH for that reason.

### Units

The app displays Fahrenheit; every formula is Celsius. Conversion happens only
at `thermal.py`'s boundary (`f_to_c` / `c_to_f`), so nothing inside mixes
scales. Pressure is hPa throughout.

### What this model assumes

The psychrometric conversions are exact — they reproduce Open-Meteo's own
reported dew point to 0.1 °C. Everything feeding them is assumed:
`f_local`, `U_g`, `Q_equip`, and above all `Ṡ_water`, which alone
decides whether the humidity answer is 40% or 75%. The temperature output reads
high; either less braking heat reaches the platform than 70%, or a busy station
ventilates faster than 4 ACH. This is the least validated model in the app.

## Methodology

[`METHODOLOGY.md`](METHODOLOGY.md) is the standalone writeup of how the three
station figures are calculated — formulas, every constant, what varies between
stations, and where each model is weak. Read that if you want the science; the
rest of this README is about running the app.

## Files

- `app.py` — Streamlit UI. A single dashboard: location, platform PM2.5,
  platform temperature, platform humidity.
- `openmeteo.py` — grid dedupe, batched fetch, disk cache, metric registry,
  AQI categories. Usable on its own, without Streamlit.
- `indoor.py` — the PM2.5 mechanical source model (and the retained
  infiltration model). Pure functions, no Streamlit, no I/O.
- `thermal.py` — heat balance and psychrometrics. Also pure functions.
- `charts.py` — Altair builders and the palette.

`openmeteo.py` stands alone if you want the data without the UI:

```python
import openmeteo as om
stations = om.load_stations()
snapshot = om.fetch_snapshot(stations, ttl_hours=3)
om.station_current(snapshot, stations[stations.stop_name == "Times Sq-42 St"].iloc[0])
```

`indoor.py` is likewise standalone:

```python
import indoor, openmeteo as om
stations = om.load_stations()
station = stations[stations.stop_name == "Times Sq-42 St"].iloc[0]
source = indoor.subway_delta_c(station)     # reads structure + route_count
source.delta_c                              # 96.3 ug/m3
indoor.platform_pm25(outdoor=9.7, delta_c=source.delta_c)   # 106.0
indoor.delta_c_for_all(stations)            # all 496, for system context
```
