"""Flood exposure and mold risk for an NYC subway station.

Two different flood mechanisms are in play here, and this module keeps them
separate rather than blending them into one number, because they measure
different things and only one of them is well-matched to what floods a
subway station.

PLUVIAL (rainfall) FLOODING -- the mechanism that actually floods stations.
NYC's storm sewers are designed to a stated capacity of 1.75 in/hr (NYC DEP;
also the threshold MTA cites in its own resiliency briefings). Rain heavier
than that overwhelms the drains before it can be carried away, and that
excess is what pours down station entrances and stairwells. This module
flags every hour Open-Meteo's precipitation forecast/history crosses that
line, using ordinary weather-model precipitation -- nothing from the Flood
API is needed for this part.

FLUVIAL (river) FLOODING -- the Flood API's actual subject. It reports daily
river discharge (m3/s) for the largest river GloFAS resolves within 5 km of a
point, from the Global Flood Awareness System. This is a real, useful signal
for a station near an actual river (the Bronx River, the Harlem River), but
it is the WRONG mechanism for most of the system: GloFAS models catchment
river routing, not tidal estuaries or storm sewers, so for a station near the
Hudson or the (tidal) East River the "largest river" it finds may not be
representative of anything that would flood a platform, and some cells may
resolve to no meaningful river at all. It is surfaced here as separate,
clearly-labelled context -- never folded into the mold-risk score -- for
exactly that reason.

MOLD RISK is then built from the pluvial signal plus platform humidity, using
thresholds carried over from EPA / ASHRAE / CDC guidance rather than anything
NYC- or subway-specific, because no public dataset validates a subway-specific
number (see METHODOLOGY.md):

    - Relative humidity above ~70% is the threshold the building-science and
      EPA/ASHRAE literature converges on for active mold growth on a surface.
    - EPA/CDC/OSHA converge on 24-48 hours as the window within which drying a
      wet area prevents mold from taking hold; beyond that, growth becomes
      probable, with visible colonization typically by 48-72 hours.

Treat the result as a risk indicator built from established environmental
thresholds, not a validated forecast -- there is no public per-station mold
dataset to calibrate or check it against.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# ---------------------------------------------------------------------------
# Pluvial (rainfall) exceedance
# ---------------------------------------------------------------------------

# NYC DEP's stated storm-sewer design capacity, and the figure MTA's own
# resiliency briefings cite as the threshold above which the system floods.
SEWER_CAPACITY_IN_PER_HR = 1.75
MM_PER_IN = 25.4
SEWER_CAPACITY_MM_PER_HR = SEWER_CAPACITY_IN_PER_HR * MM_PER_IN  # 44.45 mm/hr

# ---------------------------------------------------------------------------
# Mold risk thresholds
#
# Not NYC-specific and not subway-specific -- these are the general building-
# science / public-health figures (EPA, ASHRAE, CDC, OSHA), used because no
# subway-specific number exists to use instead.
# NOTE BY US: THIS DATA DOES NOT EXIST. Instead, we are pulling the general
# mold germination cycle based on humidity and flood data. Mold has a higher
# likelihood to grow in humidity > 60%, so we have an indicator for when it is
# more likely to grow--this differs at every station.
# ---------------------------------------------------------------------------

MOLD_RH_CAUTION = 60.0    # ASHRAE's stated ceiling; growth stalls below this
MOLD_RH_ACTIVE = 70.0     # consensus critical RH for active surface mold growth
DRY_WINDOW_HOURS = 48.0   # EPA/CDC/OSHA: dry within this window and growth is
                          # preventable; beyond it, growth becomes probable


@dataclass(frozen=True)
class MoldRisk:
    level: str            # "Low" | "Caution" | "Elevated" | "High"
    description: str


def _mold_risk(hours_since_flood: float | None, rh_in: float | None) -> MoldRisk:
    """The two-rule model: humidity alone, sharpened by a recent flood event.

    No flood in the lookback window -> read humidity on its own, the ordinary
    ASHRAE/EPA bands. A flood in the window sharpens the read: still inside
    the 24-48h drying window and dry -> the event was survived; past the
    window, or wet regardless of the window, -> elevated/high.
    """
    rh = rh_in if rh_in is not None and not pd.isna(rh_in) else None

    if hours_since_flood is None:
        if rh is None:
            return MoldRisk("Low", "No recent flood signal and no humidity reading.")
        if rh >= MOLD_RH_ACTIVE:
            return MoldRisk(
                "Elevated",
                f"No recent flood, but sustained humidity ({rh:.0f}%) is already "
                f"above the {MOLD_RH_ACTIVE:.0f}% active-growth threshold.",
            )
        if rh >= MOLD_RH_CAUTION:
            return MoldRisk(
                "Caution",
                f"Humidity ({rh:.0f}%) is in the {MOLD_RH_CAUTION:.0f}-"
                f"{MOLD_RH_ACTIVE:.0f}% caution band; risk depends on how long it stays there.",
            )
        return MoldRisk("Low", f"Humidity ({rh:.0f}%) is below the {MOLD_RH_CAUTION:.0f}% caution band.")

    if hours_since_flood <= DRY_WINDOW_HOURS and rh is not None and rh < MOLD_RH_CAUTION:
        return MoldRisk(
            "Low",
            f"Flood exceedance {hours_since_flood:.0f}h ago, but humidity has already "
            f"dropped below {MOLD_RH_CAUTION:.0f}% inside the {DRY_WINDOW_HOURS:.0f}h drying window.",
        )
    if hours_since_flood > DRY_WINDOW_HOURS or (rh is not None and rh >= MOLD_RH_ACTIVE):
        return MoldRisk(
            "High",
            f"Flood exceedance {hours_since_flood:.0f}h ago -- "
            + (
                f"past the {DRY_WINDOW_HOURS:.0f}h drying window, growth is now probable."
                if hours_since_flood > DRY_WINDOW_HOURS
                else f"and humidity ({rh:.0f}%) is above the {MOLD_RH_ACTIVE:.0f}% active-growth threshold."
            ),
        )
    return MoldRisk(
        "Elevated",
        f"Flood exceedance {hours_since_flood:.0f}h ago, still inside the "
        f"{DRY_WINDOW_HOURS:.0f}h drying window -- outcome depends on whether the area dries in time.",
    )


def pluvial_exceedances(precip_hourly: pd.DataFrame) -> pd.DataFrame:
    """Hours where precipitation crossed the sewer-capacity threshold.

    `precip_hourly` is `openmeteo.station_precipitation_series`'s output
    (columns: time, precipitation_mm). Returns the subset that exceeds
    `SEWER_CAPACITY_MM_PER_HR`, sorted oldest first.
    """
    if precip_hourly.empty:
        return precip_hourly
    exceeded = precip_hourly[precip_hourly["precipitation_mm"] > SEWER_CAPACITY_MM_PER_HR]
    return exceeded.sort_values("time").reset_index(drop=True)


def hours_since_last_exceedance(
    precip_hourly: pd.DataFrame, *, now: pd.Timestamp | None = None
) -> float | None:
    """Hours since the most recent pluvial exceedance, or None if there wasn't one."""
    exceeded = pluvial_exceedances(precip_hourly)
    if exceeded.empty:
        return None
    now = now if now is not None else pd.Timestamp.now(tz=exceeded["time"].dt.tz)
    last = exceeded["time"].iloc[-1]
    return max(0.0, (now - last).total_seconds() / 3600.0)


# ---------------------------------------------------------------------------
# River discharge context (GloFAS, via the Flood API) -- informational only
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RiverDischargeContext:
    available: bool
    latest_m3s: float | None
    baseline_median_m3s: float | None
    anomaly_pct: float | None       # latest vs. the fetched window's median
    elevated: bool                  # anomaly_pct beyond ELEVATED_ANOMALY_PCT
    note: str


ELEVATED_ANOMALY_PCT = 50.0   # latest discharge this far above the window median


def river_discharge_context(flood_daily: pd.DataFrame) -> RiverDischargeContext:
    """Where today's discharge sits relative to the fetched window's median.

    This is deliberately coarse -- a percentile against a two-week window, not
    a return-period flood stage -- because GloFAS's own historical baseline
    is not fetched here (see FLOOD_PAST_DAYS in openmeteo.py). It answers "is
    this higher than the last couple of weeks", not "is this a flood".
    """
    series = flood_daily["river_discharge"].dropna() if not flood_daily.empty else pd.Series(dtype=float)
    if series.empty:
        return RiverDischargeContext(
            available=False, latest_m3s=None, baseline_median_m3s=None,
            anomaly_pct=None, elevated=False,
            note="GloFAS did not resolve a river within 5 km of this station -- "
                 "common for stations away from the Bronx River, Harlem River, or "
                 "other mapped waterways. Not meaningful for most of the system; "
                 "see flood.py.",
        )

    latest = float(series.iloc[-1])
    baseline = float(series.median())
    anomaly = ((latest - baseline) / baseline * 100.0) if baseline > 0 else None
    elevated = anomaly is not None and anomaly >= ELEVATED_ANOMALY_PCT
    return RiverDischargeContext(
        available=True, latest_m3s=latest, baseline_median_m3s=baseline,
        anomaly_pct=anomaly, elevated=elevated,
        note="GloFAS river discharge -- a fluvial (river) signal, not the pluvial "
             "(storm-sewer) mechanism that actually floods most stations. Context "
             "only; excluded from the mold-risk score.",
    )


# ---------------------------------------------------------------------------
# Combined result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FloodClimate:
    threshold_mm_hr: float
    latest_precip_mm: float | None
    exceeded_today: bool
    hours_since_exceedance: float | None
    mold: MoldRisk
    river: RiverDischargeContext


def station_flood_climate(
    precip_hourly: pd.DataFrame,
    flood_daily: pd.DataFrame,
    *,
    rh_in: float | None,
    enclosed: bool = True,
    now: pd.Timestamp | None = None,
) -> FloodClimate:
    """Everything the UI needs for one station's flood/mold panel.

    `enclosed` gates the mold verdict, and it matters more than it looks.
    The RH thresholds below describe damp persisting against a surface in a
    poorly-ventilated space. An open-air platform is handed STREET humidity,
    which in NYC sits at 72-84% on an ordinary day -- above both thresholds --
    so without this gate every elevated, viaduct and at-grade station reads
    "Elevated" on a day when nothing is wrong. Measured across the system that
    was all 174 open-air stations, while zero enclosed stations moved: the
    signal was entirely an artefact of which stations get street air.

    Rainfall exceedance is still reported for open-air stations, because that
    is a real property of the location; only the mold verdict is suppressed.
    """
    hours_since = hours_since_last_exceedance(precip_hourly, now=now)
    latest_precip = (
        float(precip_hourly["precipitation_mm"].iloc[-1])
        if not precip_hourly.empty and pd.notna(precip_hourly["precipitation_mm"].iloc[-1])
        else None
    )
    return FloodClimate(
        threshold_mm_hr=SEWER_CAPACITY_MM_PER_HR,
        latest_precip_mm=latest_precip,
        exceeded_today=hours_since is not None and hours_since < 24.0,
        hours_since_exceedance=hours_since,
        mold=(
            _mold_risk(hours_since, rh_in)
            if enclosed
            else MoldRisk(
                "Low",
                "Open-air station — no enclosed volume for damp to persist in. "
                "The humidity here is the street's, which is not a mould signal.",
            )
        ),
        river=river_discharge_context(flood_daily),
    )


MOLD_LEVEL_ORDER = ("Low", "Caution", "Elevated", "High")

# Mold mapped onto the dashboard's 1-5 station scale. It stops at 4: mold is a
# chronic exposure that develops over days, so it should never on its own drive
# a station to 5 ("Severe"), which is reserved for acute conditions a worker
# meets on the shift -- an extreme heat index, or particulates far past the
# guideline.
MOLD_TO_LEVEL: dict[str, int] = {"Low": 1, "Caution": 2, "Elevated": 3, "High": 4}