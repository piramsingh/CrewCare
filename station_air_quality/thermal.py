"""Outdoor -> platform temperature and humidity for an underground station.

Same skeleton as the PM2.5 model in `indoor.py` -- a source divided by a
ventilation rate -- but with two differences that matter.

HEAT HAS A SECOND SINK. Dust leaves only with the air; heat also conducts into
the tunnel shell and the ground around it. That ground term is what compresses
the seasonal swing: platforms run far above the street in January and only a
little above it in July.

    T_in = (Q_internal + C_vent*T_out + UA*T_ground) / (C_vent + UA)

HUMIDITY CANNOT BE MODELLED AS RH. Relative humidity is a ratio against a
saturation capacity that moves with temperature, so heating air changes its RH
without adding or removing a single molecule of water. Warming today's 18.1 C /
67% street air to platform temperature drops it to ~44% RH with zero moisture
added. So the chain has to run through absolute moisture:

    outdoor (T, RH or dewpoint) -> vapour pressure -> mixing ratio w
    w_in = w_out + S_water / mdot_air
    T_in from the heat balance above
    (T_in, w_in) -> back to RH and dewpoint

UNITS. The app displays Fahrenheit, but every formula here is Celsius. All
conversion happens at this module's boundary -- `f_to_c` on the way in,
`c_to_f` on the way out -- so nothing inside mixes scales. Pressure is hPa
throughout and is never unit-converted.

TIME SCALE. Unlike PM2.5 (time constant ~15 min, so a steady-state formula
applied to hourly data is fine), the tunnel shell is a thermal flywheel with a
time constant of about 6 days. A platform does not follow this hour's street
temperature; it follows a trailing mean. `effective_outdoor_temperature` builds
that from a month of daily means, and it is what drives the heat balance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

import indoor

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------

RHO_AIR = 1.2          # kg/m3
CP_AIR = 1005.0        # J/(kg K)
RHO_SHELL = 2400.0     # kg/m3, concrete / rock
CP_SHELL = 900.0       # J/(kg K)
P_STANDARD = 1013.25   # hPa, fallback only

# ---------------------------------------------------------------------------
# Fixed configuration. Constants by design, exactly as in indoor.py: the app
# exposes no control over them, so every station is compared on identical terms.
# ---------------------------------------------------------------------------

TRAIN_MASS_KG = 400_000.0      # loaded 10-car consist
ENTRY_SPEED_MS = 50 / 3.6      # 50 km/h approaching the platform
BRAKE_FRACTION_LOCAL = 0.70    # share of braking energy released in/near the station
CONSIST_AC_W = 250_000.0       # car A/C heat rejected while the train is in the station
DWELL_SECONDS = 40.0
PASSENGERS = 150
HEAT_PER_PERSON_W = 100.0
EQUIPMENT_W = 30_000.0         # lighting, fans, escalators, signalling

U_GROUND = 1.5                 # W/(m2 K), air -> shell -> surrounding earth
SHELL_DEPTH_M = 1.0            # depth of shell participating in the thermal mass

# Ground temperature is CALIBRATED, not assumed, because the one thing everyone
# knows about NYC platforms is that they are never cold. The anchor below fixes
# the quietest enclosed station at 55 F in the coldest weather; the ground
# temperature that produces it is solved from the heat balance itself, so if any
# other constant changes the anchor still holds.
#
# Virgin earth at depth would be ~13 C (NYC's annual mean air temperature), but
# the tunnels have been shedding heat into the surrounding ground for over a
# century, so the earth a station actually touches is far warmer than virgin
# ground. The solved value lands near 21 C, independently consistent with that.
COLD_BASELINE_PLATFORM_F = 55.0   # what the platform reads in the coldest weather
COLD_STREET_F = 30.0              # what "coldest weather" means, as a trailing mean
BASELINE_TRAINS_PER_HOUR = 9.0    # the quietest enclosed station: 1 route
BASELINE_ACH = 4.0

# MOISTURE: dewpoint conservation is the baseline.
#
# Platform level is unconditioned and ventilated by the piston effect pulling
# street air through. Nothing dehumidifies it, so absolute moisture -- dewpoint,
# or equivalently mixing ratio -- passes through approximately unchanged. What
# does NOT pass through is relative humidity: the same water in warmer air reads
# as a much lower percentage, so using outdoor RH directly would overstate
# humidity underground badly.
#
# So the model conserves dewpoint and lets RH fall out of the indoor temperature.
# The two known deviations are kept as named, separately switchable terms rather
# than folded into the baseline, because neither is measured here:
#
#   SEEPAGE_G_S   groundwater infiltration evaporating off wet tunnel surfaces.
#                 Real in many NYC stations and it only ADDS moisture. Default 0
#                 so the shipped model is the defensible first-order one; set it
#                 to ~12 g/s to explore a wet-tunnel station.
#   PASSENGERS    respiration, computed from the same constant the heat balance
#                 uses. Measured at ~0.4 F of dewpoint for a full platform, i.e.
#                 negligible, which is why conservation holds as well as it does.
#
# Condensation, the third deviation, needs no parameter: it is handled exactly by
# the saturation cap in station_climate, which is the only term that can REMOVE
# moisture.
#
# Treat conservation as a first-order model to validate, not a fact.
SEEPAGE_G_S = 0.0
INCLUDE_PASSENGER_RESPIRATION = True
RESPIRATION_G_PER_PERSON_HOUR = 50.0


def f_to_c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


def c_to_f(c: float) -> float:
    return c * 9.0 / 5.0 + 32.0


def delta_f_from_delta_c(dc: float) -> float:
    """A temperature DIFFERENCE, not a temperature. No 32 offset."""
    return dc * 9.0 / 5.0


# ---------------------------------------------------------------------------
# Psychrometrics (all Celsius / hPa)
# ---------------------------------------------------------------------------


def saturation_vapour_pressure(t_c: float) -> float:
    """Magnus/Bolton, hPa. Reproduces Open-Meteo's own dewpoint to 0.1 C."""
    return 6.112 * math.exp(17.67 * t_c / (t_c + 243.5))


def vapour_pressure_from_rh(t_c: float, rh: float) -> float:
    return rh / 100.0 * saturation_vapour_pressure(t_c)


def vapour_pressure_from_dewpoint(dewpoint_c: float) -> float:
    """Preferred route: the API reports dewpoint directly, so no RH round-trip."""
    return saturation_vapour_pressure(dewpoint_c)


def mixing_ratio(e_hpa: float, p_hpa: float = P_STANDARD) -> float:
    """Grams of water per kilogram of dry air."""
    return 621.97 * e_hpa / (p_hpa - e_hpa)


def vapour_pressure_from_mixing_ratio(w: float, p_hpa: float = P_STANDARD) -> float:
    return w * p_hpa / (621.97 + w)


def dewpoint_from_vapour_pressure(e_hpa: float) -> float:
    gamma = math.log(e_hpa / 6.112)
    return 243.5 * gamma / (17.67 - gamma)


def wet_bulb_c(t_c: float, rh: float) -> float:
    """Psychrometric wet-bulb temperature, degC (Stull 2011).

    Valid roughly 5-99% RH and -20..50 C. NOTE this is the fully ventilated
    wet bulb; WBGT formally wants the NATURAL wet bulb, which runs warmer in
    still air. A platform between trains is close to still, so the WBGT below
    is an underestimate -- see `wbgt_indoor_c`.
    """
    return (
        t_c * math.atan(0.151977 * (rh + 8.313659) ** 0.5)
        + math.atan(t_c + rh)
        - math.atan(rh - 1.676331)
        + 0.00391838 * rh**1.5 * math.atan(0.023101 * rh)
        - 4.686035
    )


def wbgt_indoor_c(t_c: float, rh: float) -> float:
    """Wet Bulb Globe Temperature for a no-solar-load setting, degC.

        indoors / no sun:  WBGT = 0.7*T_nwb + 0.3*T_globe
        outdoors, sun:     WBGT = 0.7*T_nwb + 0.2*T_globe + 0.1*T_air

    The indoor form applies underground, and the globe term simplifies: with no
    sun, mean radiant temperature is close to air temperature, so T_globe ~=
    T_air and the two formulas converge. That is what makes WBGT -- the metric
    ACGIH and NIOSH heat guidance is written against -- reachable here without a
    globe thermometer.

    Two ways this runs LOW, both unsafe-side, so do not read a value just under
    a threshold as clearance:
      - still air raises the natural wet bulb above the psychrometric one
        (roughly +1 to +2 C on a quiet platform);
      - standing at the platform edge after a train has braked is a hotter
        radiant environment than T_globe = T_air assumes.
    """
    return 0.7 * wet_bulb_c(t_c, rh) + 0.3 * t_c


# Plain-language bands for dew point, the standard meteorological comfort scale.
# Dew point is used rather than RH because it is the quantity that actually
# tracks mugginess: 60 F dew point feels the same whatever the air temperature,
# whereas 60% RH feels completely different at 60 F and at 95 F.
DEWPOINT_BANDS: tuple[tuple[float, str], ...] = (
    (55.0, "Dry"),
    (60.0, "Comfortable"),
    (65.0, "Noticeably humid"),
    (70.0, "Muggy"),
    (75.0, "Oppressive"),
    (999.0, "Sweltering"),
)


def dewpoint_band(dewpoint_f: float) -> str:
    for ceiling, label in DEWPOINT_BANDS:
        if dewpoint_f < ceiling:
            return label
    return DEWPOINT_BANDS[-1][1]


def heat_index_f(t_f: float, rh: float) -> float:
    """Rothfusz apparent temperature, degF. Below ~80 F it degenerates, so the
    simple average form is used there instead, as NWS specifies."""
    simple = 0.5 * (t_f + 61.0 + (t_f - 68.0) * 1.2 + rh * 0.094)
    if (simple + t_f) / 2 < 80.0:
        return simple
    hi = (
        -42.379 + 2.04901523 * t_f + 10.14333127 * rh
        - 0.22475541 * t_f * rh - 6.83783e-3 * t_f**2
        - 5.481717e-2 * rh**2 + 1.22874e-3 * t_f**2 * rh
        + 8.5282e-4 * t_f * rh**2 - 1.99e-6 * t_f**2 * rh**2
    )
    if rh < 13 and 80 <= t_f <= 112:
        hi -= ((13 - rh) / 4) * math.sqrt((17 - abs(t_f - 95)) / 17)
    elif rh > 85 and 80 <= t_f <= 87:
        hi += ((rh - 85) / 10) * ((87 - t_f) / 5)
    return hi


# ---------------------------------------------------------------------------
# Heat balance
# ---------------------------------------------------------------------------


def shell_area(box: indoor.StationBox) -> float:
    """All six faces of the box exchange heat with the surrounding structure."""
    return 2 * (box.length * box.height + box.width * box.height + box.length * box.width)


def q_braking(trains_per_hour: float) -> float:
    """W. Kinetic energy destroyed per stop, times stops per hour."""
    energy = 0.5 * TRAIN_MASS_KG * ENTRY_SPEED_MS**2
    return trains_per_hour * energy * BRAKE_FRACTION_LOCAL / 3600.0


def q_train_ac(trains_per_hour: float) -> float:
    """W. Cooling the passengers heats the station, but only during the dwell."""
    return trains_per_hour * CONSIST_AC_W * DWELL_SECONDS / 3600.0


def q_internal(trains_per_hour: float) -> dict[str, float]:
    """Every heat source, itemised so the UI can show the budget."""
    return {
        "Braking": q_braking(trains_per_hour),
        "Lighting and equipment": EQUIPMENT_W,
        "Passengers": PASSENGERS * HEAT_PER_PERSON_W,
        "Train A/C": q_train_ac(trains_per_hour),
    }


def ventilation_capacity_rate(air_changes: float, volume: float) -> float:
    """W/K. How much heat one kelvin of excess carries out with the air."""
    return RHO_AIR * CP_AIR * volume * air_changes / 3600.0


def ground_conductance(box: indoor.StationBox) -> float:
    """W/K."""
    return U_GROUND * shell_area(box)


def air_mass_flow(air_changes: float, volume: float) -> float:
    """kg of dry air per second."""
    return RHO_AIR * volume * air_changes / 3600.0


def thermal_time_constant(air_changes: float, box: indoor.StationBox) -> float:
    """Seconds. Shell thermal mass over total conductance."""
    shell = shell_area(box) * SHELL_DEPTH_M * RHO_SHELL * CP_SHELL
    total = ventilation_capacity_rate(air_changes, box.volume()) + ground_conductance(box)
    return shell / total if total > 0 else float("inf")


def _solve_ground_temperature() -> float:
    """Ground temperature (C) implied by the cold-weather anchor.

    Inverts  T_in = (Q + C_vent*T_out + UA*T_ground) / (C_vent + UA)
    for T_ground, at the baseline station in the coldest weather.
    """
    box = indoor.BOX
    c_vent = ventilation_capacity_rate(BASELINE_ACH, box.volume())
    ua = ground_conductance(box)
    if ua <= 0:
        return 13.0
    q = sum(q_internal(BASELINE_TRAINS_PER_HOUR).values())
    lift_c = q / (c_vent + ua)
    street_weight = c_vent / (c_vent + ua)
    ground_weight = ua / (c_vent + ua)
    target_c = f_to_c(COLD_BASELINE_PLATFORM_F)
    street_c = f_to_c(COLD_STREET_F)
    return (target_c - street_weight * street_c - lift_c) / ground_weight


GROUND_TEMPERATURE_C = _solve_ground_temperature()


def effective_outdoor_temperature(daily_means_c: list[float], tau_seconds: float) -> float:
    """Exponentially weighted trailing mean of daily outdoor temperature.

    The platform's driver. Using the current hour instead would make the
    estimate swing with the street when the real platform barely moves.
    """
    if not daily_means_c:
        return float("nan")
    alpha = 1.0 - math.exp(-86400.0 / tau_seconds)
    value = daily_means_c[0]
    for entry in daily_means_c:
        value += alpha * (entry - value)
    return value


# ---------------------------------------------------------------------------
# The station result
# ---------------------------------------------------------------------------


@dataclass
class StationClimate:
    """Everything the UI needs, in the units it will display (F, %, hPa)."""

    enclosed: bool
    trains_per_hour: float
    air_changes: float
    volume: float

    heat_sources_w: dict[str, float]
    q_total_w: float
    c_vent_w_k: float
    ua_ground_w_k: float
    tau_days: float

    t_out_f: float              # current street temperature
    t_effective_f: float        # trailing mean actually driving the balance
    t_in_f: float
    delta_t_f: float

    rh_out: float
    rh_in: float
    dewpoint_out_f: float
    dewpoint_in_f: float
    w_out: float                # g/kg
    w_in: float
    moisture_source_g_s: float
    condensing: bool

    heat_index_out_f: float
    heat_index_in_f: float
    wet_bulb_in_f: float
    wbgt_in_c: float
    dewpoint_shift_f: float     # platform minus street; 0.0 under conservation


def station_climate(
    station: pd.Series,
    *,
    t_out_f: float,
    rh_out: float,
    dewpoint_out_f: float | None,
    pressure_hpa: float | None,
    daily_means_f: list[float],
) -> StationClimate:
    """Platform temperature and humidity for one spine station.

    Ventilation and service come from the same two spine fields the PM2.5 model
    uses, via `indoor`: `structure` -> ACH and `route_count` -> trains/hour.
    """
    box = indoor.BOX
    enclosure = indoor.enclosure_for(station["structure"])
    trains_per_hour = indoor.trains_per_hour_for(station["route_count"])
    volume = box.volume()
    pressure = pressure_hpa if pressure_hpa else P_STANDARD

    t_out_c = f_to_c(t_out_f)

    # Outdoor moisture. Dewpoint is the direct measurement, so prefer it and
    # fall back to RH only when the field is missing.
    if dewpoint_out_f is not None and not pd.isna(dewpoint_out_f):
        e_out = vapour_pressure_from_dewpoint(f_to_c(dewpoint_out_f))
    else:
        e_out = vapour_pressure_from_rh(t_out_c, rh_out)
    w_out = mixing_ratio(e_out, pressure)

    sources = q_internal(trains_per_hour)
    q_total = sum(sources.values())

    if not enclosure.is_enclosed():
        # Open air: no box to heat and no box to humidify. The platform is the
        # street, so every term passes through unchanged.
        return StationClimate(
            enclosed=False, trains_per_hour=trains_per_hour, air_changes=0.0,
            volume=volume, heat_sources_w=sources, q_total_w=q_total,
            c_vent_w_k=0.0, ua_ground_w_k=0.0, tau_days=0.0,
            t_out_f=t_out_f, t_effective_f=t_out_f, t_in_f=t_out_f, delta_t_f=0.0,
            rh_out=rh_out, rh_in=rh_out,
            dewpoint_out_f=c_to_f(dewpoint_from_vapour_pressure(e_out)),
            dewpoint_in_f=c_to_f(dewpoint_from_vapour_pressure(e_out)),
            w_out=w_out, w_in=w_out, moisture_source_g_s=0.0, condensing=False,
            heat_index_out_f=heat_index_f(t_out_f, rh_out),
            heat_index_in_f=heat_index_f(t_out_f, rh_out),
            wet_bulb_in_f=c_to_f(wet_bulb_c(t_out_c, rh_out)),
            wbgt_in_c=wbgt_indoor_c(t_out_c, rh_out),
            dewpoint_shift_f=0.0,
        )

    ach = enclosure.air_changes
    c_vent = ventilation_capacity_rate(ach, volume)
    ua = ground_conductance(box)
    tau = thermal_time_constant(ach, box)

    # The driver is the trailing mean, not the current hour.
    daily_c = [f_to_c(v) for v in daily_means_f if v is not None and not pd.isna(v)]
    t_eff_c = effective_outdoor_temperature(daily_c, tau) if daily_c else t_out_c

    t_in_c = (q_total + c_vent * t_eff_c + ua * GROUND_TEMPERATURE_C) / (c_vent + ua)

    # Moisture balance, same form as the PM2.5 source model.
    moisture_g_s = SEEPAGE_G_S + (
        PASSENGERS * RESPIRATION_G_PER_PERSON_HOUR / 3600.0
        if INCLUDE_PASSENGER_RESPIRATION else 0.0
    )
    w_in = w_out + moisture_g_s / air_mass_flow(ach, volume)

    e_in = vapour_pressure_from_mixing_ratio(w_in, pressure)
    e_sat_in = saturation_vapour_pressure(t_in_c)
    condensing = e_in > e_sat_in
    # Air cannot hold more than saturation; the excess deposits on surfaces.
    e_in = min(e_in, e_sat_in)
    rh_in = 100.0 * e_in / e_sat_in

    t_in_f = c_to_f(t_in_c)
    return StationClimate(
        enclosed=True, trains_per_hour=trains_per_hour, air_changes=ach,
        volume=volume, heat_sources_w=sources, q_total_w=q_total,
        c_vent_w_k=c_vent, ua_ground_w_k=ua, tau_days=tau / 86400.0,
        t_out_f=t_out_f, t_effective_f=c_to_f(t_eff_c), t_in_f=t_in_f,
        delta_t_f=t_in_f - t_out_f,
        rh_out=rh_out, rh_in=rh_in,
        dewpoint_out_f=c_to_f(dewpoint_from_vapour_pressure(e_out)),
        dewpoint_in_f=c_to_f(dewpoint_from_vapour_pressure(e_in)),
        w_out=w_out, w_in=mixing_ratio(e_in, pressure),
        moisture_source_g_s=moisture_g_s, condensing=condensing,
        heat_index_out_f=heat_index_f(t_out_f, rh_out),
        heat_index_in_f=heat_index_f(t_in_f, rh_in),
        wet_bulb_in_f=c_to_f(wet_bulb_c(t_in_c, rh_in)),
        wbgt_in_c=wbgt_indoor_c(t_in_c, rh_in),
        dewpoint_shift_f=(
            c_to_f(dewpoint_from_vapour_pressure(e_in))
            - c_to_f(dewpoint_from_vapour_pressure(e_out))
        ),
    )


def apply_to_hourly(
    hourly: pd.DataFrame,
    station: pd.Series,
    *,
    daily_means_f: list[float],
) -> pd.DataFrame:
    """Street vs platform temperature and RH across the hourly series.

    The heat balance is driven by the trailing mean, so the platform
    temperature barely moves hour to hour -- that flatness against a swinging
    street line is the model's central claim, not a rendering artefact.
    """
    wide = (
        hourly[hourly["metric"].isin(["temperature_2m", "relative_humidity_2m",
                                      "dew_point_2m", "surface_pressure"])]
        .pivot_table(index="time", columns="metric", values="value")
        .reset_index()
    )
    if wide.empty or "temperature_2m" not in wide:
        return pd.DataFrame(columns=["time", "metric", "value", "exposure"])

    rows = []
    for _, hour in wide.iterrows():
        climate = station_climate(
            station,
            t_out_f=hour["temperature_2m"],
            rh_out=hour.get("relative_humidity_2m", float("nan")),
            dewpoint_out_f=hour.get("dew_point_2m"),
            pressure_hpa=hour.get("surface_pressure"),
            daily_means_f=daily_means_f,
        )
        rows += [
            {"time": hour["time"], "metric": "temperature_2m",
             "value": hour["temperature_2m"], "exposure": STREET_LABEL},
            {"time": hour["time"], "metric": "temperature_2m",
             "value": climate.t_in_f, "exposure": PLATFORM_LABEL},
            {"time": hour["time"], "metric": "relative_humidity_2m",
             "value": climate.rh_out, "exposure": STREET_LABEL},
            {"time": hour["time"], "metric": "relative_humidity_2m",
             "value": climate.rh_in, "exposure": PLATFORM_LABEL},
        ]
    return pd.DataFrame(rows)


STREET_LABEL = indoor.STREET_LABEL
PLATFORM_LABEL = indoor.PLATFORM_LABEL
