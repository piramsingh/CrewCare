# How the three station figures are calculated

The dashboard shows three modelled values for a chosen NYC subway station:
**PM2.5**, **temperature** and **humidity**. None is measured. Each takes a live
outdoor reading and transforms it using a physical model of the station.

This document states each model, its inputs, and where it is weak.

---

## The common shape

All three models start from the same place: a station is a fixed volume of air
that ventilation replaces at a finite rate. Whether the station *adds* anything
to that air decides which model applies.

| quantity | does the station produce it? | model |
|---|---|---|
| PM2.5 | **yes** — wheel and brake wear | `C_in = C_out + ΔC` |
| heat | **yes** — braking, equipment, people | balance of sources against two sinks |
| moisture | no | conserved from outdoors |

Relative humidity is the exception that traps people: it is not conserved, not
because moisture is lost but because RH is a *ratio* against a temperature-
dependent capacity. It is derived last, from conserved moisture and modelled
temperature.

### What varies between stations

Only two fields from `datasets/nyc_subway_station_spine.csv`, plus the live
weather:

| field | drives | values |
|---|---|---|
| `structure` | ventilation rate (ACH) | `Subway` → 4.0 · `Open Cut` → 12.0 · `Elevated`/`Viaduct`/`At Grade`/`Embankment` → open air |
| `route_count` | trains per hour | 1–4 routes × 9/h → 9, 18, 27, 36 |

Every other coefficient below is a constant, identical at all 496 stations.

Open-air stations (174 of 496) skip the enclosed-station models entirely: with
no roof there is no volume to accumulate anything in, so all three figures equal
the street values.

---

## 1 · PM2.5

Trains generate iron-rich particulate through wheel-rail wear and brake
abrasion. That mass enters a fixed volume which ventilation clears at a finite
rate, so it reaches a steady concentration above street level.

```
S_train = n · [ w·m_w·t_cruise + b·m_b·t_brake ]
ΔC      = S_train / (V · ACH)
C_in    = C_out + ΔC
```

| term | meaning | value |
|---|---|---|
| `n` | trains per hour | `route_count` × 9 |
| `w`, `b` | wheels, brake pads | 80, 80 (10-car R160/R211) |
| `m_w` | µg/s shed per wheel, cruising | 40 |
| `m_b` | µg/s shed per pad, braking | 36 |
| `t_cruise`, `t_brake` | seconds per pass | 40, 15 |
| `V` | platform volume | 160 × 15 × 5 m = 12,000 m³ |
| `ACH` | air changes per hour | from `structure` |
| `C_out` | street PM2.5 | live, Open-Meteo |

At the defaults one train pass injects **171.2 mg**. A 1-route station
(9 trains/h) generates 1.54 g/h into 48,000 m³/h of airflow, giving
**ΔC = 32.1 µg/m³**.

Because `ΔC` depends only on `structure` and `route_count`, all 496 stations
collapse onto **seven values**:

| ΔC (µg/m³) | enclosure | routes | stations |
|---|---|---|---|
| 128.4 | enclosed | 4 | 16 |
| 96.3 | enclosed | 3 | 30 |
| 64.2 | enclosed | 2 | 103 |
| 32.1 | enclosed | 1 | 134 |
| 32.1 | open cut | 3 | 1 |
| 21.4 | open cut | 2 | 4 |
| 10.7 | open cut | 1 | 34 |
| 0 | open air | any | 174 |

### Weaknesses

- **Removal is by ventilation only.** The formula uses `V·ACH`. A fuller balance
  would also drain the source through deposition, `S/(V·(ACH+k))`, putting ΔC
  somewhat lower.
- **Output runs below the only reference points available.** Against the
  literature-reported figures carried in `transitguard/app.py`, the model reads
  ~2× low for a typical underground station, and much lower at 181 St and
  168 St — both among the deepest in the system, which is the model's blind spot
  (see *Depth*, below).
- **Route count is a poor proxy for train traffic.** 181 St is a 1-route station
  the model therefore scores at the minimum, while the reference figure puts it
  among the worst in the system.
- **Emission factors are unvalidated.** ΔC is linear in `m_w` and `m_b`; a
  factor-of-two error there is a factor-of-two error in the output.

---

## 2 · Temperature

Stopping a train converts its kinetic energy to heat. Add equipment, passengers
and the trains' own air conditioning, and a platform is a room with a permanent
heater. Two sinks remove that heat: ventilation carrying it out, and conduction
into the tunnel shell and surrounding ground.

```
T_in = ( Q_internal + C_vent·T_out + UA·T_ground ) / ( C_vent + UA )
```

which rearranges to a more readable form — a weighted blend of two temperatures
plus a lift:

```
T_in = (street weight × T_out) + (ground weight × T_ground) + Q_internal/(C_vent + UA)
```

### Heat sources

```
Q_brake = n · ½mv² · f_local / 3600     m = 400,000 kg, v = 13.89 m/s, f_local = 0.70
Q_ac    = n · 250 kW · 40 s / 3600
Q_people = 150 × 100 W
Q_equip  = 30 kW
```

At 9 trains/h: braking 67.5 kW, equipment 30, A/C 25, people 15 →
**Q_internal = 137.5 kW**. Braking dominates; one stop dissipates **38.6 MJ**.

### Heat sinks

```
C_vent = ρ·c_p·V·ACH / 3600      ρ = 1.2 kg/m³, c_p = 1005 J/(kg·K)
UA     = U_g · A_shell           U_g = 1.5 W/(m²·K), A_shell = 6,550 m²
```

At 4 ACH: `C_vent` = 16.1 kW/K, `UA` = 9.8 kW/K, total 25.9 kW/K. The blend is
therefore **62% street, 38% ground**, and the heat lift is
137.5 / 25.9 = **9.6 °F**.

### `T_ground` is calibrated, not assumed

Virgin earth at depth sits near 13 °C (NYC's annual mean air temperature), but
the tunnels have been shedding heat into the surrounding ground for over a
century, so a station touches far warmer earth than that.

Rather than guess, the heat balance is inverted against one anchor — **the
quietest enclosed station reads 55 °F in the coldest weather** (1 route,
9 trains/h, street trailing mean 30 °F) — and solved for the ground
temperature that produces it:

```
55.0 = 0.621 × 30 + 0.379 × T_ground + 9.6   →   T_ground = 70.7 °F = 21.5 °C
```

21.5 °C is independently consistent with a century-heated tunnel surround.
`_solve_ground_temperature()` recomputes this at import, so changing any other
constant preserves the anchor.

### `T_out` is a trailing mean, not the current hour

The tunnel shell is a thermal flywheel:

```
τ = A_shell · depth · ρ_shell · c_shell / (C_vent + UA)  ≈  6.3 days
```

So the model is driven by an exponentially weighted mean of **daily** outdoor
temperature (α = 0.147 per day), not the live reading. This is why a separate
31-day daily-mean request exists. Using the current hour would produce a
platform that swings with the weather, which real platforms do not do.

For comparison, PM2.5 re-equilibrates in `1/ACH` ≈ 15 minutes, which is why that
model uses the live reading directly.

### Resulting platform temperatures

| street | 1 route | 2 routes | 3 routes | 4 routes |
|---|---|---|---|---|
| 30 °F | **55.0** | 61.4 | 67.9 | 74.3 |
| 50 °F | 67.4 | 73.8 | 80.3 | 86.7 |
| 70 °F | 79.8 | 86.3 | 92.7 | 99.1 |
| 88 °F | 91.0 | 97.4 | 103.9 | 110.3 |

### Weaknesses

- **The seasonal swing is probably too wide.** The platform moves 36 °F across a
  year against the street's 58 °F. That ratio is fixed by
  `C_vent/(C_vent+UA)` = 0.62 and is *not* affected by `T_ground`, which shifts
  the whole curve without compressing it. If real platforms hold a narrower band,
  the fix is a larger `UA` relative to `C_vent` — plausibly because the model
  treats the "ground" as passive earth and has no term for the connected tunnel
  network, which is both a large heat reservoir and directly coupled by the
  piston effect.
- **`f_local` = 0.70 is a guess**, and much braking heat plausibly goes into the
  tunnels rather than the station box.
- **Express vs terminal stations are indistinguishable.** A station where trains
  pass at speed has a completely different heat budget from one where every train
  brakes to a stand. The spine records neither.

---

## 3 · Humidity

### The rule that makes this work

Platform level is unconditioned and ventilated by street air drawn through by
the piston effect. **Nothing underground dehumidifies it**, so absolute moisture
— dew point, or equivalently mixing ratio — passes through approximately
unchanged.

Relative humidity does **not** transfer. It is a percentage of a capacity that
grows with temperature, so the same water in warmer air reads much lower. Using
outdoor RH directly overstates platform humidity by **25–40 percentage points**.

So: conserve dew point, model temperature, derive RH last.

### The chain

```
1.  e_out  = e_sat(T_dew)                          ← from dew_point_2m, preferred
           = (RH_out/100) · e_sat(T_out)           ← fallback
    where e_sat(T) = 6.112 · exp(17.67·T / (T + 243.5))      [hPa, °C]

2.  w_out  = 621.97 · e_out / (p − e_out)          [g water / kg dry air]

3.  w_in   = w_out + Ṡ_water / ṁ_air,   ṁ_air = ρ·V·ACH/3600

4.  T_in   from the temperature model above

5.  e_in   = w_in·p / (621.97 + w_in)
    e_in   = min(e_in, e_sat(T_in))                ← saturation cap
    RH_in  = 100 · e_in / e_sat(T_in)
    γ = ln(e_in/6.112);  T_dew,in = 243.5·γ / (17.67 − γ)
```

`p` is the live `surface_pressure`, not a constant.

### The source term is zero by default

`Ṡ_water` has three components, kept separable because none is measured:

| component | status | why |
|---|---|---|
| groundwater seepage | **`SEEPAGE_G_S = 0.0`** | real in many NYC stations, but unmeasured; set to ~12 g/s to model a wet-tunnel station |
| passenger respiration | on, 150 × 50 g/h | measured at **+0.41 °F** of dew point — negligible, which is *why* conservation holds |
| condensation | automatic | handled exactly by the saturation cap, the only term that can remove moisture |

So the shipped model is strict dew-point conservation plus a negligible
respiration term. **Treat conservation as a first-order model to validate, not a
fact.**

### Validation

The Magnus implementation reproduces Open-Meteo's own reported dew point to
0.1 °C, and the `w ↔ e` conversion inverts to zero error. The psychrometric
machinery is exact; only the source term is assumed.

### What the model predicts

Platforms come out **hot and dry**, not hot and muggy — an enclosed station at
85 °F reads around 26–39% RH, below the 40–60% band normally considered healthy
indoors. Two consequences:

- For heat stress this is *favourable*: dry air lets sweat evaporate, so
  feels-like sits at or slightly below air temperature.
- Dry air has its own cost, and it compounds the PM2.5 exposure: it irritates
  airways and impairs the mucociliary clearance that removes inhaled particles.

This conclusion is contingent on `SEEPAGE_G_S = 0`. If NYC tunnels are
substantially wet, platforms become hot *and* muggy and feels-like rises sharply
— at a 3-route station on an 85 °F day, from 117 °F to 134 °F at 10× seepage.
That is the single parameter most worth measuring.

### On displaying humidity

Relative humidity is sound for one station read on its own, but it must not be
used to rank stations. Across the 496, RH correlates with heat risk at
**−0.984** — near-perfectly inverted, because it is temperature in disguise. The
highest-RH stations (Arthur Kill, Tottenville, 75%) are open-air Staten Island
stops, among the safest in the system; the most dangerous are 4-route
underground hubs at ~21% RH.

Dew point does not have that flaw but carries almost no station-level signal:
it spans only **5.1 °F** across all 496 stations today, and 0.2 °F under uniform
summer conditions, because it is conserved from a 35-cell weather grid.

For ranking or risk, use **feels-like** (Rothfusz heat index) or **WBGT**, both
computed in `thermal.py`. Underground, WBGT simplifies usefully: with no solar
load, mean radiant temperature ≈ air temperature, so the globe term collapses
and `WBGT = 0.7·T_wb + 0.3·T_air`. Note this runs **low** — WBGT formally wants
the *natural* wet bulb, which exceeds the ventilated one by 1–2 °C in the still
air of a platform between trains. Do not read a value just under a threshold as
clearance.

---

## Limitations that apply to all three

**Nothing here is measured.** Every model is honest arithmetic on assumed
coefficients. No public per-station feed exists for the NYC subway; the closest
real platform measurements (35 platforms, 30 stations, 2019) are NYU Langone
dataset 10479, which is access-on-request.

**The outdoor inputs are coarse.** Open-Meteo's air-quality model resolves to a
0.1° grid (~11 km) and its weather model to ~0.05° (~5 km). All 496 stations
fall into **15 air-quality cells** and **35 weather cells**, so stations within
about 11 km of each other receive identical outdoor air quality by construction.

**Depth is absent from the data.** Every underground station carries the single
`structure` value `Subway`, so all 283 take the same ventilation rate. The
plausible proxies fail on inspection: 191 St, among the deepest in the system,
lists 2 entrances while shallow Bergen St lists 6, and `platform_to_street_m` is
a horizontal offset, not a depth. A deep rock-bored station traps air far more
than a shallow cut-and-cover box, and none of these models can see that.

**Service level is assumed.** The spine has no timetable — its only service
field is `route_count`. Trains per hour is `route_count × 9`, a flat rate
implying ~13-minute headways each way, so the models cannot distinguish rush
hour from a Sunday. Real per-stop frequencies would come from MTA GTFS
`stop_times.txt`; this is the highest-value data addition available.

**The station is treated as one well-mixed box.** Real platforms have strong
gradients between trackbed and mezzanine, and ventilation is pulsed by train
arrivals rather than steady.

**The enclosure classes are a judgment.** `structure` supplies six raw values;
collapsing them into enclosed / trench / open air, and the ACH attached to each,
is not from the dataset. The spine ships its own `structure_group`, which these
models do **not** use — it groups `Embankment` with `Open Cut`, whereas a raised
earth embankment is open air for ventilation purposes. That affects 6 stations.
The 12.0 ACH for an open cut is likewise a judgment: the data says the trench is
roofless, nothing quantifies the exchange rate.

---

## Where the code lives

| file | contents |
|---|---|
| `openmeteo.py` | live outdoor readings, grid dedupe, disk cache, metric registry |
| `indoor.py` | PM2.5 source model; retained infiltration model (unused by the UI) |
| `thermal.py` | heat balance, psychrometrics, wet bulb, WBGT, heat index |
| `app.py` | the dashboard |

A refresh costs three HTTP requests for the entire system — air quality, hourly
weather, and 31 days of daily means — cached to disk for 3 hours.
