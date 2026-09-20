"""Models for estimating air quality inside an underground subway station.

Two models live here.

MECHANICAL SOURCE MODEL (what the app shows)
--------------------------------------------
Platform PM2.5 is dominated by particles generated underground, not by street
air leaking in. Wheel-rail wear and brake-pad abrasion inject iron-rich mass
into a fixed volume that ventilation clears at a finite rate, so:

    S_train = trains/h * [ wheels * m_w * t_cruise  +  pads * m_b * t_brake ]
    Q_total = V * ACH
    dC      = S_train / Q_total
    C_in    = C_out + dC

`dC` is the steady-state concentration the station's own machinery sustains
above whatever the street is doing. Because the source term does not depend on
C_out, it acts as a near-constant offset: platform PM2.5 tracks the street's
shape but sits far above its level.

Note this follows the supplied formulation exactly, in which ventilation is the
only removal path (`Q_total = V * ACH`). A fuller balance would also drain the
source through deposition, `S/(V*(ACH + k))`, which would put dC somewhat lower.

INFILTRATION MODEL (retained, not currently surfaced)
-----------------------------------------------------
    C_in = C_out * (P * a) / (a + k)

The steady state of a mass balance with no source term: it answers how much of
the STREET's particle load persists underground, and is capped at P <= 1. It is
kept here because it is still the right model for outdoor-origin pollutants and
because the PM10 platform estimate was built on it, but the app's Underground
tab now uses the mechanical source model above for PM2.5 only.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ParticleParams:
    """Size-dependent terms. P and k are properties of the particle, not the space."""

    penetration: float      # P, dimensionless 0-1
    deposition: float       # k, 1/h
    p_range: tuple[float, float]
    k_range: tuple[float, float]


# Air exchange is a property of the enclosure, so it is shared across pollutants.
DEFAULT_AIR_EXCHANGE = 3.0          # a, 1/h
AIR_EXCHANGE_RANGE = (0.1, 15.0)

DEFAULTS: dict[str, ParticleParams] = {
    "pm2_5": ParticleParams(
        penetration=0.80, deposition=0.20, p_range=(0.0, 1.0), k_range=(0.0, 3.0)
    ),
    "pm10": ParticleParams(
        penetration=0.50, deposition=1.00, p_range=(0.0, 1.0), k_range=(0.0, 3.0)
    ),
}

MODELLED_METRICS = tuple(DEFAULTS)


def infiltration_factor(penetration: float, air_exchange: float, deposition: float) -> float:
    """F = P*a/(a + k), the equilibrium outdoor-origin fraction.

    Returns 0 when a + k is 0, the degenerate case of a sealed volume in which
    nothing enters and nothing settles; the steady state is then undefined and
    zero is the safe reading.
    """
    denominator = air_exchange + deposition
    if denominator <= 0:
        return 0.0
    return penetration * air_exchange / denominator


def indoor_concentration(
    outdoor: float | None, penetration: float, air_exchange: float, deposition: float
) -> float | None:
    """C_in = C_out * F. Propagates a missing outdoor value rather than faking one."""
    if outdoor is None or pd.isna(outdoor):
        return None
    return float(outdoor) * infiltration_factor(penetration, air_exchange, deposition)


def factors(
    params: dict[str, ParticleParams], air_exchange: float
) -> dict[str, float]:
    """Infiltration factor per modelled pollutant, at one air exchange rate."""
    return {
        key: infiltration_factor(p.penetration, air_exchange, p.deposition)
        for key, p in params.items()
    }


def apply_to_hourly(
    hourly: pd.DataFrame,
    params: dict[str, ParticleParams],
    air_exchange: float,
) -> pd.DataFrame:
    """Long frame of outdoor vs modelled-underground series for the PM metrics.

    Returns columns: time, metric, value, exposure ("Street level" |
    "Underground estimate").
    """
    subset = hourly[hourly["metric"].isin(params)][["time", "metric", "value"]]
    if subset.empty:
        return pd.DataFrame(columns=["time", "metric", "value", "exposure"])

    outdoor = subset.assign(exposure="Street level")
    scale = {
        key: infiltration_factor(p.penetration, air_exchange, p.deposition)
        for key, p in params.items()
    }
    indoor = subset.assign(
        value=subset["value"] * subset["metric"].map(scale),
        exposure="Underground estimate",
    )
    return pd.concat([outdoor, indoor], ignore_index=True)


def sensitivity_curve(
    params: dict[str, ParticleParams],
    *,
    at: float | None = None,
    low: float = AIR_EXCHANGE_RANGE[0],
    high: float = AIR_EXCHANGE_RANGE[1],
    steps: int = 120,
) -> pd.DataFrame:
    """F against air exchange rate -- the parameter users are least sure of.

    F rises steeply while a is small relative to k, then flattens towards its
    ceiling of P. Where a curve has gone flat, a better estimate of `a` will not
    change the answer; where it is still climbing, it will.
    """
    grid = [low + (high - low) * index / steps for index in range(steps + 1)]
    # Sample the operating point exactly. Without it the marker snaps to the
    # nearest grid point and can disagree with the headline figure by a point.
    if at is not None:
        grid.append(at)
    rows = []
    for a in sorted(set(grid)):
        for key, p in params.items():
            rows.append(
                {
                    "air_exchange": a,
                    "metric": key,
                    "factor": infiltration_factor(p.penetration, a, p.deposition),
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Mechanical source model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrainConfig:
    """Rolling stock and how long it spends generating particles per pass.

    Defaults describe a 10-car R160/R211 consist: 80 wheels and 80 brake pads.
    The emission factors are per-wheel and per-pad rates in micrograms per
    second, applied only over the seconds that mechanism is actually active.
    """

    wheels: int = 80
    brake_pads: int = 80
    wheel_emission: float = 40.0        # ug/s per wheel, cruising or idling
    brake_emission: float = 36.0        # ug/s per pad, actively braking
    cruise_seconds: float = 40.0        # s near the platform per pass
    braking_seconds: float = 15.0       # s decelerating into the station

    def mass_per_train(self) -> float:
        """Micrograms of PM2.5 injected by one train pass."""
        cruise = self.wheels * self.wheel_emission * self.cruise_seconds
        braking = self.brake_pads * self.brake_emission * self.braking_seconds
        return cruise + braking


@dataclass(frozen=True)
class StationBox:
    """Platform treated as a rectangular well-mixed volume.

    Defaults are a standard NYC platform: ~525 ft long, 15 m wide, 5 m high.
    """

    length: float = 160.0
    width: float = 15.0
    height: float = 5.0

    def volume(self) -> float:
        return self.length * self.width * self.height


# ---------------------------------------------------------------------------
# Ventilation from the station spine
#
# `structure` in nyc_subway_station_spine.csv is the only ventilation-relevant
# field the dataset actually carries. It resolves the enclosure class cleanly
# -- roofed box, open trench, or open air -- which is what V*ACH needs.
#
# IT DOES NOT RESOLVE DEPTH. All 283 underground stations share the single
# value "Subway"; there is no shallow/deep split anywhere in the file, and the
# plausible proxies fail on inspection (191 St, among the deepest in the
# system, lists 2 entrances, while shallow Bergen St lists 6; and
# platform_to_street_m is a horizontal offset from platform centroid to street
# centroid, not a depth -- 191 St's 158 m is the length of its access tunnel).
# So enclosed stations all take the system-average 4.0 ACH rather than a
# fabricated 6.0/2.5 shallow-deep assignment.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Enclosure:
    """How a structure class ventilates, and what that means in plain terms."""

    air_changes: float | None      # None = open air, no enclosed volume
    summary: str
    plain: str

    def is_enclosed(self) -> bool:
        return self.air_changes is not None


OPEN_AIR = Enclosure(
    air_changes=None,
    summary="Open air \u2014 no enclosed volume",
    plain="The platform is out in the open, so brake and wheel dust blows away "
          "instead of building up. There is no box for it to accumulate in.",
)

STRUCTURE_ENCLOSURE: dict[str, Enclosure] = {
    "Subway": Enclosure(
        air_changes=4.0,
        summary="Enclosed box below grade",
        plain="A roofed, walled room underground. Air only turns over through "
              "stairwells, passageways and sidewalk grates, so dust from the "
              "trains accumulates.",
    ),
    "Open Cut": Enclosure(
        air_changes=12.0,
        summary="Trench open to the sky",
        plain="Walls on both sides but no roof, so dust disperses upward far "
              "faster than in a tunnel \u2014 though not as freely as at street level.",
    ),
    "Embankment": OPEN_AIR,
    "Elevated": OPEN_AIR,
    "Viaduct": OPEN_AIR,
    "At Grade": OPEN_AIR,
}

# 12.0 ACH for an open cut is a judgment, not a measurement: the dataset tells
# us the trench is roofless, and a roofless trench plainly exchanges air far
# faster than a tunnel, but nothing in the file quantifies by how much.

DEFAULT_ENCLOSURE = STRUCTURE_ENCLOSURE["Subway"]

# The fixed configuration. These are constants by design: the app exposes no
# control over them, so every station on screen is compared on identical
# emission assumptions.
TRAIN = TrainConfig()
BOX = StationBox()

# Trains per hour per route, counting BOTH directions.
#
# This is an assumption, not data: the spine carries no frequency, headway or
# schedule field of any kind (its only service column is `route_count`). 9/h
# both ways is one train roughly every 13 minutes in each direction -- an
# off-peak-ish level, on the sparse side of typical NYC daytime service. Real
# per-stop frequencies would have to come from MTA GTFS `stop_times.txt`.
#
# Held constant, so service varies across stations only through `route_count`.
TRAINS_PER_ROUTE_PER_HOUR = 9.0


def implied_headway_minutes(trains_per_hour_per_route: float = TRAINS_PER_ROUTE_PER_HOUR) -> float:
    """Minutes between trains in ONE direction, implied by the rate above.

    Exists so the assumption states its own consequence on screen: a trains/h
    figure is easy to nod at, a headway in minutes is easy to sanity-check.
    """
    per_direction = trains_per_hour_per_route / 2
    return 60.0 / per_direction if per_direction > 0 else float("inf")


def enclosure_for(structure: str) -> Enclosure:
    return STRUCTURE_ENCLOSURE.get(structure, DEFAULT_ENCLOSURE)


def trains_per_hour_for(route_count: float) -> float:
    """Service level implied by how many routes the spine lists at a station."""
    return float(route_count) * TRAINS_PER_ROUTE_PER_HOUR


@dataclass(frozen=True)
class SubwaySource:
    """Every intermediate in the dC calculation, so the UI can show the chain."""

    structure: str
    enclosure: Enclosure
    route_count: float
    trains_per_hour: float
    mass_per_train: float      # ug
    mass_hourly: float         # ug/h
    volume: float              # m3
    air_changes: float         # 1/h
    airflow: float             # m3/h
    delta_c: float             # ug/m3

    def grams_hourly(self) -> float:
        return self.mass_hourly / 1e6


def subway_delta_c(station: pd.Series) -> SubwaySource:
    """PM2.5 the trains sustain above street level at one spine station.

    Everything except the station's own `structure` and `route_count` is held
    constant: the consist, the emission factors, the durations and the platform
    box are all fixed module-level values, so two stations differ only through
    what the dataset actually says about them.
    """
    train = TRAIN
    box = BOX
    enclosure = enclosure_for(station["structure"])
    trains_per_hour = trains_per_hour_for(station["route_count"])

    mass_per_train = train.mass_per_train()
    mass_hourly = mass_per_train * trains_per_hour
    volume = box.volume()

    if not enclosure.is_enclosed():
        # No roof, no box, no accumulation. Reporting a large-but-finite dC
        # here would imply a measurement of open air that this model cannot make.
        return SubwaySource(
            structure=station["structure"],
            enclosure=enclosure,
            route_count=station["route_count"],
            trains_per_hour=trains_per_hour,
            mass_per_train=mass_per_train,
            mass_hourly=mass_hourly,
            volume=volume,
            air_changes=0.0,
            airflow=0.0,
            delta_c=0.0,
        )

    airflow = volume * enclosure.air_changes
    return SubwaySource(
        structure=station["structure"],
        enclosure=enclosure,
        route_count=station["route_count"],
        trains_per_hour=trains_per_hour,
        mass_per_train=mass_per_train,
        mass_hourly=mass_hourly,
        volume=volume,
        air_changes=enclosure.air_changes,
        airflow=airflow,
        delta_c=mass_hourly / airflow,
    )


def delta_c_for_all(stations: pd.DataFrame) -> pd.DataFrame:
    """dC for every station in the spine, for system-wide context."""
    rows = [
        {
            "gtfs_stop_id": station["gtfs_stop_id"],
            "stop_name": station["stop_name"],
            "structure": station["structure"],
            "route_count": station["route_count"],
            "enclosure": enclosure_for(station["structure"]).summary,
            "delta_c": subway_delta_c(station).delta_c,
        }
        for _, station in stations.iterrows()
    ]
    return pd.DataFrame(rows)


def platform_pm25(outdoor: float | None, delta_c: float) -> float | None:
    """C_in = C_out + dC, propagating a missing outdoor value."""
    if outdoor is None or pd.isna(outdoor):
        return None
    return float(outdoor) + delta_c


PM25_KEY = "pm2_5"
STREET_LABEL = "Street level"
PLATFORM_LABEL = "Platform estimate"


def apply_pm25_to_hourly(hourly: pd.DataFrame, delta_c: float) -> pd.DataFrame:
    """Long frame of street vs platform PM2.5, for the hourly chart."""
    subset = hourly[hourly["metric"] == PM25_KEY][["time", "metric", "value"]]
    if subset.empty:
        return pd.DataFrame(columns=["time", "metric", "value", "exposure"])
    street = subset.assign(exposure=STREET_LABEL)
    platform = subset.assign(value=subset["value"] + delta_c, exposure=PLATFORM_LABEL)
    return pd.concat([street, platform], ignore_index=True)
