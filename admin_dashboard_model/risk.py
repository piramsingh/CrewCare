"""A 1-5 station risk level, and worker-specific precautions.

THREE AXES
----------
    axis 1: platform PM2.5        (from indoor.py)
    axis 2: heat index            (from thermal.py; temperature AND humidity)
    axis 3: mould risk            (from flood.py; rainfall AND humidity)

Relative humidity is never an axis of its own. It acts on a worker through two
distinct mechanisms, and each is scored where it belongs: it impairs sweat
evaporation, which is the heat index, and it lets mould grow on surfaces, which
is axis 3. Scoring RH directly would rank stations backwards -- across the 496 it
correlates with heat risk at -0.984, because platform RH is mostly temperature in
disguise.

The two humidity paths are not double counting: they respond to opposite ends of
the range. High temperature drives RH down, so a station tends to score on heat
OR on mould, rarely both. Taking the maximum means whichever applies is the one
that surfaces -- and it is what lets the scale finally distinguish a cool, damp
station from a cool, dry one, which the two-axis version rated identically.

Mould is capped at 4 (see flood.MOLD_TO_LEVEL): it develops over days, so it
should not on its own declare a station "Severe", which is reserved for acute
conditions met on the shift.

COMBINED BY MAXIMUM, NOT AVERAGE
--------------------------------
A station that is fine on heat and severe on particulates is not "moderate". It
is severe, and the reason matters for what the worker should do about it.
Averaging hides exactly the case the scale exists to catch.

NOT A CLINICAL INSTRUMENT
-------------------------
The inputs are modelled, not measured, so a level is a planning prior for
scheduling and precautions -- not a basis for clearing a station as safe, and
not medical advice for any individual.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import flood

# ---------------------------------------------------------------------------
# Bands
# ---------------------------------------------------------------------------

LEVEL_NAMES: dict[int, str] = {
    1: "Low",
    2: "Caution",
    3: "Elevated",
    4: "High",
    5: "Severe",
}

# Status palette, shared with charts.py. Level 5 extends past the four status
# roles into the deep red the AQI scale has trained people to read.
LEVEL_COLORS: dict[int, str] = {
    1: "#0ca30c",
    2: "#fab219",
    3: "#ec835a",
    4: "#d03b3b",
    5: "#6b1420",
}

# PM2.5 ceilings in ug/m3, anchored on published guidance rather than invented:
#   15  WHO 24-hour guideline
#   35  US EPA 24-hour PM2.5 standard
# The upper two bands extend the same spacing; they exist so the scale does not
# saturate at a hub on a bad air day.
PM25_CEILINGS: tuple[tuple[float, int], ...] = (
    (15.0, 1),
    (35.0, 2),
    (75.0, 3),
    (150.0, 4),
    (float("inf"), 5),
)

# Heat-index ceilings in degF, following the US National Weather Service
# heat-index categories: below 80 no caution, 80-90 Caution, 90-103 Extreme
# Caution, 103-125 Danger, 125+ Extreme Danger.
HEAT_CEILINGS: tuple[tuple[float, int], ...] = (
    (80.0, 1),
    (90.0, 2),
    (103.0, 3),
    (125.0, 4),
    (float("inf"), 5),
)


def _level_from(value: float | None, ceilings: tuple[tuple[float, int], ...]) -> int | None:
    if value is None:
        return None
    for ceiling, level in ceilings:
        if value < ceiling:
            return level
    return ceilings[-1][1]


def pm25_level(platform_pm25: float | None) -> int | None:
    return _level_from(platform_pm25, PM25_CEILINGS)


def heat_level(heat_index_f: float | None) -> int | None:
    return _level_from(heat_index_f, HEAT_CEILINGS)


def mould_level(mould_risk_level: str | None) -> int:
    """Map flood.py's four-step mould verdict onto this 1-5 scale."""
    if not mould_risk_level:
        return 1
    return flood.MOLD_TO_LEVEL.get(mould_risk_level, 1)


@dataclass
class StationRisk:
    """The 1-5 level, plus which axis drove it and why."""

    level: int
    name: str
    color: str
    pm25_level: int
    heat_level: int
    mould_level: int
    platform_pm25: float
    heat_index_f: float
    mould_risk: str
    driver: str                 # the axis or axes at the top level
    reasons: list[str] = field(default_factory=list)


def station_risk(
    platform_pm25: float | None,
    heat_index_f: float | None,
    mould_risk_level: str | None = None,
    mould_reason: str | None = None,
) -> StationRisk:
    pm = pm25_level(platform_pm25) or 1
    heat = heat_level(heat_index_f) or 1
    mould = mould_level(mould_risk_level)
    level = max(pm, heat, mould)

    # Name every axis that reaches the top, so the driver never hides a
    # co-equal hazard behind whichever one happened to be checked first.
    axes = [
        name for name, value in
        (("Particulates", pm), ("Heat", heat), ("Mould", mould))
        if value == level
    ]
    if level == 1:
        # At the floor every axis ties, but nothing is "driving" anything.
        driver = "Nothing elevated"
    elif len(axes) == 1:
        driver = axes[0]
    else:
        driver = " and ".join([", ".join(axes[:-1]), axes[-1]])

    reasons = []
    if platform_pm25 is not None:
        reasons.append(
            f"Platform PM2.5 {platform_pm25:.0f} µg/m³ — "
            f"{platform_pm25 / 15.0:.1f}× the WHO 24-hour guideline"
        )
    if heat_index_f is not None:
        reasons.append(f"Feels like {heat_index_f:.0f} °F on the platform")
    if mould_risk_level and mould > 1:
        reasons.append(f"Mould risk {mould_risk_level.lower()}"
                       + (f" — {mould_reason}" if mould_reason else ""))

    return StationRisk(
        level=level, name=LEVEL_NAMES[level], color=LEVEL_COLORS[level],
        pm25_level=pm, heat_level=heat, mould_level=mould,
        platform_pm25=platform_pm25 if platform_pm25 is not None else float("nan"),
        heat_index_f=heat_index_f if heat_index_f is not None else float("nan"),
        mould_risk=mould_risk_level or "Low",
        driver=driver, reasons=reasons,
    )


# ---------------------------------------------------------------------------
# Worker overlay
# ---------------------------------------------------------------------------


@dataclass
class WorkerProfile:
    """The factors that change a worker's threshold at the same station.

    Deliberately small. Each field below has a documented mechanism; anything
    that would need a clinician to interpret is out of scope.
    """

    respiratory_condition: bool = False   # asthma, COPD, other obstructive disease
    cardiovascular_condition: bool = False
    heat_sensitising_medication: bool = False
    shift_hours: float = 8.0
    overnight_tour: bool = False


@dataclass
class WorkerRisk:
    station: StationRisk
    level: int
    name: str
    color: str
    uplift: int
    modifiers: list[str] = field(default_factory=list)
    precautions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def worker_risk(station: StationRisk, profile: WorkerProfile) -> WorkerRisk:
    """Adjust a station level for one worker, and say what to do about it.

    The uplift is capped at +1. It marks "this worker crosses a threshold
    sooner than the general population", not a quantified dose-response, which
    nothing here supports.
    """
    modifiers: list[str] = []
    notes: list[str] = []
    uplift = 0

    if profile.respiratory_condition and max(station.pm25_level, station.mould_level) >= 2:
        uplift = 1
        modifiers.append(
            "Obstructive respiratory condition — inhaled particulates and mould "
            "spores both provoke symptoms at levels the general population tolerates."
        )
    if profile.cardiovascular_condition and station.level >= 2:
        uplift = 1
        modifiers.append(
            "Cardiovascular condition — both particulate and heat strain raise "
            "cardiac demand."
        )
    if profile.heat_sensitising_medication and station.heat_level >= 2:
        uplift = 1
        modifiers.append(
            "Medication that impairs thermoregulation — several common classes "
            "(diuretics, beta blockers, anticholinergics, antipsychotics) reduce "
            "the body's ability to shed heat."
        )
    if profile.shift_hours >= 8 and station.level >= 3:
        modifiers.append(
            f"{profile.shift_hours:.0f}-hour tour — exposure is a dose, and the "
            "station level describes concentration, not time spent in it."
        )

    level = min(5, station.level + uplift)

    if profile.overnight_tour:
        notes.append(
            "**Overnight tour — the station figures overstate this worker's "
            "exposure.** Both models assume a flat 9 trains per route per hour; "
            "overnight service is far thinner, which lowers both the particulate "
            "source and the braking heat. At ~4 trains/route/hour the PM2.5 the "
            "trains add falls by more than half."
        )
        notes.append(
            "Overnight is also when diesel work equipment runs. That is a real "
            "CO and particulate source in an enclosed station, and it is invisible "
            "to every model here — nothing in the data knows where a work train is."
        )

    return WorkerRisk(
        station=station, level=level, name=LEVEL_NAMES[level],
        color=LEVEL_COLORS[level], uplift=uplift, modifiers=modifiers,
        precautions=precautions_for(station, profile, level), notes=notes,
    )


def precautions_for(
    station: StationRisk, profile: WorkerProfile, level: int
) -> list[str]:
    """Occupational precautions, escalating with level.

    These are workplace controls of the kind a safety programme issues, not
    medical advice. Nothing here tells anyone to change a treatment.
    """
    out: list[str] = []

    if level <= 1:
        out.append("No special precautions indicated for this shift.")
        return out

    if station.pm25_level >= 2:
        out.append(
            "Spend break time at street level or in the booth rather than on the "
            "platform — the particulate source is the trains, so exposure drops "
            "sharply away from the trackbed."
        )
    if station.pm25_level >= 3:
        out.append(
            "Consider a fitted N95 for sustained platform work. Iron-rich brake "
            "and rail dust is a fine particulate; a surgical mask does not filter it."
        )
    if station.pm25_level >= 4:
        out.append(
            "Escalate to a supervisor: sustained platform assignments at this level "
            "warrant rotation off the platform rather than personal protection alone."
        )

    if station.heat_level >= 2:
        out.append(
            "Pre-hydrate and carry water. Platform air is warmer and drier than the "
            "street, so fluid loss is faster than it feels."
        )
    if station.heat_level >= 3:
        out.append(
            "Build in rest in a cooler area. NIOSH heat guidance is written as "
            "work/rest minutes per hour, not as a yes/no threshold."
        )
    if station.heat_level >= 4:
        out.append(
            "Do not work alone on the platform. At this level, buddy checks for "
            "heat-illness symptoms are the standard control."
        )

    if station.mould_level >= 2:
        out.append(
            "Report damp, staining or standing water through the station's "
            "condition log. Mould is a maintenance fix — drying the area within "
            "24-48 hours prevents growth; personal protection does not."
        )

    if profile.respiratory_condition:
        out.append(
            "Carry the rescue inhaler on shift rather than leaving it in a locker, "
            "and log puffs used — a work-versus-off difference in rescue use is the "
            "clearest signal that the workplace is driving symptoms."
        )
        if station.pm25_level >= 3:
            out.append(
                "Record peak flow at the start and end of the tour. A drop across "
                "the shift is the measurement an occupational clinician will want."
            )

    return out
