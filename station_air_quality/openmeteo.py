"""Open-Meteo client for the NYC subway station air-quality app.

Three verified facts shape this module (checked 2026-09-19 by round-tripping
coordinates through the live API and reading back the lat/lon it echoes):

1. The air-quality model snaps to a 0.1 deg grid (~11 km); the weather model to
   roughly 0.05 deg (~5 km). All 496 stations in the spine therefore collapse to
   15 air-quality cells and 35 weather cells.
2. Open-Meteo accepts comma-separated coordinate lists and returns one object
   per location, in request order.
3. `past_days` + `forecast_days` give a single hourly series spanning history
   and forecast in one call.

Together those mean a whole-city snapshot -- current conditions plus a 5-day
hourly series for every station -- costs exactly TWO HTTP requests, ~250 KB.
A third request adds 31 days of daily temperature means (the thermal model's
trailing-mean input), and a fourth adds 14 days of daily river discharge from
the Flood API (GloFAS) for the mold-risk model in flood.py. Everything else
here exists to make sure we spend those four and then leave the API alone
until the TTL expires. Both a process-local memory cache (the caller wraps
these in st.cache_data) and an on-disk JSON cache are used, so restarting the
app inside the TTL window refetches nothing.

No API key is required for Open-Meteo's free non-commercial tier.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
DEFAULT_SPINE = REPO_ROOT / "datasets" / "nyc_subway_station_spine.csv"
CACHE_DIR = APP_DIR / ".cache"

AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"

TIMEZONE = "America/New_York"
PAST_DAYS = 2
FORECAST_DAYS = 3

# A separate, much longer window of DAILY means, used only to drive the thermal
# model. A platform's temperature follows a trailing mean with a ~6-day time
# constant, so two days of hourly history cannot resolve it. Daily values keep
# this cheap: 31 days x 35 cells is ~30 KB, against ~1.5 MB for the same span
# of hourly data, which is why it is a third request rather than a wider second.
DAILY_PAST_DAYS = 31

# The flood model looks back far enough to catch the mold-risk decay window
# (EPA/CDC: growth risk rises over the ~72 hours after a wet event and mold is
# typically established by day 7-12) with a few days of margin, and asks for no
# forecast -- flood risk here is scored from what already happened, not GloFAS's
# river forecast. Daily resolution only: river discharge is a daily quantity in
# this API regardless of what is requested.
FLOOD_PAST_DAYS = 14
FLOOD_FORECAST_DAYS = 1

# Model grid resolutions, in degrees. Sampling finer than this buys nothing but
# API calls: the service interpolates to the same cell and echoes back the same
# snapped coordinate.
AQ_RESOLUTION = 0.1
WX_RESOLUTION = 0.05
# GloFAS resolves to ~5 km, the same as the weather grid, so the flood API
# shares WX_RESOLUTION rather than defining its own.
FLOOD_RESOLUTION = WX_RESOLUTION

DEFAULT_TTL_HOURS = 3
REQUEST_TIMEOUT = 60


# ---------------------------------------------------------------------------
# Metric registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Metric:
    """One measurable quantity, and everything the UI needs to render it."""

    key: str
    label: str
    unit: str
    source: str  # "aq" (air-quality model) or "wx" (weather model)
    decimals: int = 1
    hourly: bool = True
    note: str = ""

    def format(self, value: float | None) -> str:
        if value is None or pd.isna(value):
            return "n/a"
        return f"{value:,.{self.decimals}f}"

    def format_with_unit(self, value: float | None) -> str:
        text = self.format(value)
        return text if text == "n/a" or not self.unit else f"{text} {self.unit}"


UG_M3 = "µg/m³"

METRICS: tuple[Metric, ...] = (
    Metric("us_aqi", "US AQI", "", "aq", decimals=0,
           note="EPA Air Quality Index, computed by Open-Meteo from the modelled "
                "pollutant mix. Higher is worse; 50 and 100 are the Good and "
                "Moderate ceilings."),
    Metric("pm2_5", "PM2.5", UG_M3,
           source="aq",
           note="Fine inhalable particles. The WHO 24-hour guideline is 15 "
                f"{UG_M3}."),
    Metric("pm10", "PM10", UG_M3, "aq",
           note=f"Coarse inhalable particles. The WHO 24-hour guideline is 45 {UG_M3}."),
    Metric("carbon_dioxide", "CO₂", "ppm", "aq", decimals=0,
           note="Modelled CO₂ concentration. This is dominated by the global "
                "background (~420 ppm) and is a climate rather than a local "
                "air-quality signal -- read the swing, not the level."),
    Metric("carbon_monoxide", "CO", UG_M3, "aq", decimals=0,
           note="Carbon monoxide, largely traffic-derived at street level."),
    Metric("nitrogen_dioxide", "NO₂", UG_M3, "aq",
           note="Traffic and combustion marker; peaks with rush hour."),
    Metric("sulphur_dioxide", "SO₂", UG_M3, "aq",
           note="Mostly from fuel combustion and shipping."),
    Metric("ozone", "Ozone", UG_M3, "aq", decimals=0,
           note="Ground-level ozone. Photochemical, so it peaks on sunny afternoons."),
    Metric("dust", "Dust", UG_M3, "aq", hourly=False,
           note="Mineral dust fraction of particulates."),
    Metric("uv_index", "UV index", "", "aq", hourly=False,
           note="Clear-sky-adjusted UV index at the surface."),
    Metric("temperature_2m", "Air temperature", "°F", "wx",
           note="Dry-bulb air temperature 2 m above ground."),
    Metric("apparent_temperature", "Feels like", "°F", "wx",
           note="Apparent temperature, combining humidity, wind and radiation."),
    Metric("relative_humidity_2m", "Humidity", "%", "wx", decimals=0),
    Metric("dew_point_2m", "Dew point", "\u00b0F", "wx",
           note="The temperature at which this air would saturate. Unlike relative "
                "humidity it does not move when the air is heated, so it is the "
                "honest measure of how much moisture is actually present."),
    Metric("surface_pressure", "Pressure", "hPa", "wx", decimals=0,
           note="Station-level air pressure, used to convert humidity to a mixing ratio."),
    Metric("precipitation", "Precipitation", "mm", "wx", decimals=2,
           note="Rain, showers and snowmelt combined for that hour. Compared against "
                "NYC DEP's stated 1.75 in/hr (~44.5 mm/hr) storm-sewer design "
                "capacity to flag hours the system is likely to be overwhelmed -- "
                "see flood.py."),
    Metric("wind_speed_10m", "Wind", "km/h", "wx", hourly=False),
)

METRICS_BY_KEY = {m.key: m for m in METRICS}


def metrics_for(source: str, *, hourly_only: bool = False) -> list[Metric]:
    return [
        m for m in METRICS
        if m.source == source and (m.hourly or not hourly_only)
    ]


# ---------------------------------------------------------------------------
# US AQI categories
#
# Six bands, but the design system's status palette has four roles. The first
# four bands take the status roles as-is; "Very Unhealthy" and "Hazardous"
# extend into the purple/maroon the EPA scale has trained people to read. The
# category NAME is rendered next to the color everywhere, so hue never carries
# the meaning by itself.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AQICategory:
    name: str
    lower: int
    upper: int
    color: str
    advice: str


AQI_CATEGORIES: tuple[AQICategory, ...] = (
    AQICategory("Good", 0, 50, "#0ca30c",
                "Air quality is satisfactory; little or no risk."),
    AQICategory("Moderate", 51, 100, "#fab219",
                "Acceptable, but unusually sensitive people should watch for symptoms."),
    AQICategory("Unhealthy for sensitive groups", 101, 150, "#ec835a",
                "People with asthma, heart or lung conditions should limit prolonged exertion outdoors."),
    AQICategory("Unhealthy", 151, 200, "#d03b3b",
                "Everyone may begin to feel effects; sensitive groups should avoid exertion outdoors."),
    AQICategory("Very unhealthy", 201, 300, "#7d2ab5",
                "Health alert. Everyone should avoid prolonged exertion outdoors."),
    AQICategory("Hazardous", 301, 10_000, "#6b1420",
                "Emergency conditions. Stay indoors where possible."),
)


def aqi_category(value: float | None) -> AQICategory | None:
    if value is None or pd.isna(value):
        return None
    for band in AQI_CATEGORIES:
        if value <= band.upper:
            return band
    return AQI_CATEGORIES[-1]


# ---------------------------------------------------------------------------
# Stations
# ---------------------------------------------------------------------------


def _snap(value: float, resolution: float) -> float:
    return round(round(value / resolution) * resolution, 4)


def _cell_key(source: str, lat: float, lon: float, resolution: float) -> str:
    """Grid-namespaced cell id.

    The `source` prefix is load-bearing, not decoration: snapping the same point
    to 0.1 and to 0.05 degrees can land on the identical coordinate string
    (40.8000,-74.0000 is both), which without the prefix silently collides the
    two grids in a shared index.
    """
    return f"{source}:{_snap(lat, resolution):.4f},{_snap(lon, resolution):.4f}"


def cell_coordinates(cell: str) -> str:
    """The human-readable half of a cell key, without the grid prefix."""
    return cell.split(":", 1)[-1]


def load_stations(path: Path | str = DEFAULT_SPINE) -> pd.DataFrame:
    """Read the station spine and attach the model-grid cell each station falls in.

    Street coordinates are used rather than platform coordinates: the modelled
    values are ambient outdoor air, which is what a rider meets at the entrance,
    not what is in the tunnel below it.
    """
    stations = pd.read_csv(path)

    missing = {"street_latitude", "street_longitude", "stop_name"} - set(stations.columns)
    if missing:
        raise ValueError(f"{path} is missing expected columns: {sorted(missing)}")

    stations = stations.copy()
    stations["lat"] = stations["street_latitude"].fillna(stations["latitude"])
    stations["lon"] = stations["street_longitude"].fillna(stations["longitude"])
    stations["aq_cell"] = [
        _cell_key("aq", a, b, AQ_RESOLUTION)
        for a, b in zip(stations["lat"], stations["lon"])
    ]
    stations["wx_cell"] = [
        _cell_key("wx", a, b, WX_RESOLUTION)
        for a, b in zip(stations["lat"], stations["lon"])
    ]
    stations["fl_cell"] = [
        _cell_key("fl", a, b, FLOOD_RESOLUTION)
        for a, b in zip(stations["lat"], stations["lon"])
    ]

    # 117 stop names repeat across lines, so the picker label needs the routes
    # and borough too -- and the GTFS id on the handful that still collide.
    label = (
        stations["stop_name"]
        + "  ·  "
        + stations["daytime_routes"].fillna("")
        + "  ·  "
        + stations["borough"].fillna("")
    )
    duplicated = label.duplicated(keep=False)
    stations["label"] = label.where(~duplicated, label + "  (" + stations["gtfs_stop_id"] + ")")

    return stations.sort_values("label").reset_index(drop=True)


_CELL_COLUMNS = {"aq": "aq_cell", "wx": "wx_cell", "fl": "fl_cell"}


def unique_cells(stations: pd.DataFrame, source: str) -> list[tuple[float, float]]:
    """Distinct model-grid points the station set touches, in a stable order."""
    column = _CELL_COLUMNS[source]
    keys = sorted(stations[column].unique())
    return [
        tuple(float(part) for part in cell_coordinates(key).split(","))
        for key in keys
    ]


# ---------------------------------------------------------------------------
# Disk cache
# ---------------------------------------------------------------------------


def _signature(payload: object) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def _cache_path(name: str, signature: str) -> Path:
    return CACHE_DIR / f"{name}-{signature}.json"


def _read_cache(path: Path, ttl_seconds: float) -> tuple[object, datetime] | None:
    if not path.exists():
        return None
    try:
        envelope = json.loads(path.read_text())
        fetched_at = datetime.fromisoformat(envelope["fetched_at"])
    except (OSError, ValueError, KeyError):
        return None
    if (time.time() - fetched_at.timestamp()) > ttl_seconds:
        return None
    return envelope["payload"], fetched_at


def _write_cache(path: Path, payload: object, fetched_at: datetime) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    envelope = {"fetched_at": fetched_at.isoformat(), "payload": payload}
    # Write-then-rename so a crash mid-write can't leave a half-parsed cache.
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(envelope))
    temporary.replace(path)


def clear_cache() -> int:
    """Delete every cached response. Returns how many files were removed."""
    if not CACHE_DIR.exists():
        return 0
    removed = 0
    for path in CACHE_DIR.glob("*.json"):
        path.unlink(missing_ok=True)
        removed += 1
    return removed


def cache_files() -> list[Path]:
    return sorted(CACHE_DIR.glob("*.json")) if CACHE_DIR.exists() else []


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def _fetch_grid(
    *,
    url: str,
    cells: list[tuple[float, float]],
    params: dict[str, object],
    cache_name: str,
    ttl_hours: float,
    force: bool,
) -> tuple[list[dict], datetime, bool]:
    """One batched request for every cell, served from disk inside the TTL.

    Returns (payload, fetched_at, came_from_cache).
    """
    request_params = dict(params)
    request_params["latitude"] = ",".join(f"{lat:.4f}" for lat, _ in cells)
    request_params["longitude"] = ",".join(f"{lon:.4f}" for _, lon in cells)

    signature = _signature({"url": url, **request_params})
    path = _cache_path(cache_name, signature)

    if not force:
        cached = _read_cache(path, ttl_hours * 3600)
        if cached is not None:
            payload, fetched_at = cached
            return _as_list(payload), fetched_at, True

    response = requests.get(url, params=request_params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    fetched_at = datetime.now(timezone.utc)
    _write_cache(path, payload, fetched_at)
    return _as_list(payload), fetched_at, False


def _as_list(payload: object) -> list[dict]:
    """Open-Meteo returns a bare object for one location, a list for many."""
    return payload if isinstance(payload, list) else [payload]


@dataclass
class Snapshot:
    """Everything the UI needs for one refresh window."""

    current: pd.DataFrame       # one row per grid cell, indexed by cell key
    hourly: pd.DataFrame        # long: cell, time, metric, value
    daily: pd.DataFrame         # long: cell, date, t_mean -- drives the thermal lag
    flood: pd.DataFrame         # long: cell, date, river_discharge (m3/s) -- GloFAS
    fetched_at: datetime
    from_cache: bool
    requests_made: int
    cell_counts: dict[str, int]

    def age_seconds(self) -> float:
        return max(0.0, time.time() - self.fetched_at.timestamp())


def _frames_from_payload(
    payload: list[dict],
    cells: list[tuple[float, float]],
    metrics: list[Metric],
    hourly_keys: list[str],
    source: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Turn one Open-Meteo multi-location response into (current, hourly long)."""
    current_rows: list[dict] = []
    hourly_frames: list[pd.DataFrame] = []

    for (lat, lon), location in zip(cells, payload):
        cell = f"{source}:{lat:.4f},{lon:.4f}"
        current = location.get("current", {}) or {}
        row: dict[str, object] = {
            "cell": cell,
            "model_latitude": location.get("latitude"),
            "model_longitude": location.get("longitude"),
            "observed_at": current.get("time"),
        }
        for metric in metrics:
            row[metric.key] = current.get(metric.key)
        current_rows.append(row)

        hourly = location.get("hourly") or {}
        if not hourly.get("time"):
            continue
        frame = pd.DataFrame({"time": pd.to_datetime(hourly["time"])})
        for key in hourly_keys:
            if key in hourly:
                frame[key] = hourly[key]
        frame = frame.melt(id_vars="time", var_name="metric", value_name="value")
        frame["cell"] = cell
        hourly_frames.append(frame)

    current_frame = pd.DataFrame(current_rows).set_index("cell")
    hourly_frame = (
        pd.concat(hourly_frames, ignore_index=True)
        if hourly_frames
        else pd.DataFrame(columns=["time", "metric", "value", "cell"])
    )
    return current_frame, hourly_frame


def fetch_snapshot(
    stations: pd.DataFrame,
    *,
    ttl_hours: float = DEFAULT_TTL_HOURS,
    force: bool = False,
) -> Snapshot:
    """Fetch current + hourly conditions for every grid cell the stations touch.

    Two HTTP requests total, regardless of how many stations are passed in.
    """
    aq_metrics = metrics_for("aq")
    wx_metrics = metrics_for("wx")
    aq_hourly = [m.key for m in aq_metrics if m.hourly]
    wx_hourly = [m.key for m in wx_metrics if m.hourly]

    aq_cells = unique_cells(stations, "aq")
    wx_cells = unique_cells(stations, "wx")

    shared = {
        "timezone": TIMEZONE,
        "past_days": PAST_DAYS,
        "forecast_days": FORECAST_DAYS,
    }

    aq_payload, aq_time, aq_cached = _fetch_grid(
        url=AIR_QUALITY_URL,
        cells=aq_cells,
        params={
            **shared,
            "current": ",".join(m.key for m in aq_metrics),
            "hourly": ",".join(aq_hourly),
        },
        cache_name="air-quality",
        ttl_hours=ttl_hours,
        force=force,
    )
    wx_payload, wx_time, wx_cached = _fetch_grid(
        url=FORECAST_URL,
        cells=wx_cells,
        params={
            **shared,
            "current": ",".join(m.key for m in wx_metrics),
            "hourly": ",".join(wx_hourly),
            "temperature_unit": "fahrenheit",
        },
        cache_name="weather",
        ttl_hours=ttl_hours,
        force=force,
    )

    daily_payload, daily_time, daily_cached = _fetch_grid(
        url=FORECAST_URL,
        cells=wx_cells,
        params={
            "timezone": TIMEZONE,
            "past_days": DAILY_PAST_DAYS,
            "forecast_days": 1,
            "daily": "temperature_2m_mean",
            "temperature_unit": "fahrenheit",
        },
        cache_name="daily-means",
        ttl_hours=ttl_hours,
        force=force,
    )

    fl_cells = unique_cells(stations, "fl")
    # No `timezone` param here: the Flood API's documented parameter list does
    # not include one (dates come back as plain ISO calendar days, GMT), unlike
    # every other endpoint this module calls. bruh.
    flood_payload, flood_time, flood_cached = _fetch_grid(
        url=FLOOD_URL,
        cells=fl_cells, # Note: Open Meteo does NOT return NYC, it gets data based on long/lat. We are getting data based on subway loc in dataset
        params={
            "past_days": FLOOD_PAST_DAYS,
            "forecast_days": FLOOD_FORECAST_DAYS,
            "daily": "river_discharge",
        },
        cache_name="flood",
        ttl_hours=ttl_hours,
        force=force,
    )

    aq_current, aq_hourly_frame = _frames_from_payload(
        aq_payload, aq_cells, aq_metrics, aq_hourly, "aq"
    )
    wx_current, wx_hourly_frame = _frames_from_payload(
        wx_payload, wx_cells, wx_metrics, wx_hourly, "wx"
    )

    daily_frames = []
    for (lat, lon), location in zip(wx_cells, daily_payload):
        block = location.get("daily") or {}
        if not block.get("time"):
            continue
        daily_frames.append(
            pd.DataFrame({
                "cell": f"wx:{lat:.4f},{lon:.4f}",
                "date": pd.to_datetime(block["time"]),
                "t_mean": block.get("temperature_2m_mean"),
            })
        )
    daily = (
        pd.concat(daily_frames, ignore_index=True)
        if daily_frames
        else pd.DataFrame(columns=["cell", "date", "t_mean"])
    )

    flood_frames = []
    for (lat, lon), location in zip(fl_cells, flood_payload):
        block = location.get("daily") or {}
        if not block.get("time"):
            continue
        flood_frames.append(
            pd.DataFrame({
                "cell": f"fl:{lat:.4f},{lon:.4f}",
                "date": pd.to_datetime(block["time"]),
                "river_discharge": block.get("river_discharge"),
            })
        )
    flood = (
        pd.concat(flood_frames, ignore_index=True)
        if flood_frames
        else pd.DataFrame(columns=["cell", "date", "river_discharge"])
    )

    aq_current["source"] = "aq"
    wx_current["source"] = "wx"
    current = pd.concat([aq_current, wx_current])
    hourly = pd.concat([aq_hourly_frame, wx_hourly_frame], ignore_index=True)

    return Snapshot(
        current=current,
        hourly=hourly,
        daily=daily,
        flood=flood,
        # The oldest of the four responses is the honest age of the snapshot.
        fetched_at=min(aq_time, wx_time, daily_time, flood_time),
        from_cache=aq_cached and wx_cached and daily_cached and flood_cached,
        requests_made=(
            int(not aq_cached) + int(not wx_cached)
            + int(not daily_cached) + int(not flood_cached)
        ),
        cell_counts={"aq": len(aq_cells), "wx": len(wx_cells), "fl": len(fl_cells)},
    )


# ---------------------------------------------------------------------------
# Per-station views onto the snapshot
# ---------------------------------------------------------------------------


def station_current(snapshot: Snapshot, station: pd.Series) -> dict[str, float | None]:
    """Current value of every metric at one station's two grid cells."""
    values: dict[str, float | None] = {}
    for source, cell in (("aq", station["aq_cell"]), ("wx", station["wx_cell"])):
        rows = snapshot.current[snapshot.current["source"] == source]
        if cell not in rows.index:
            continue
        row = rows.loc[cell]
        for metric in metrics_for(source):
            values[metric.key] = row.get(metric.key)
    return values


def station_hourly(snapshot: Snapshot, station: pd.Series) -> pd.DataFrame:
    """Long hourly frame (time, metric, value, label, unit) for one station."""
    wanted = snapshot.hourly["cell"].isin([station["aq_cell"], station["wx_cell"]])
    frame = snapshot.hourly[wanted].copy()

    # Safe against cross-grid contamination because cell keys are namespaced
    # by grid -- see _cell_key.
    frame["label"] = frame["metric"].map(lambda k: METRICS_BY_KEY[k].label)
    frame["unit"] = frame["metric"].map(lambda k: METRICS_BY_KEY[k].unit)
    return frame.sort_values(["metric", "time"]).reset_index(drop=True)


def city_current(snapshot: Snapshot, stations: pd.DataFrame) -> pd.DataFrame:
    """Every station joined to its cell's current air-quality values."""
    aq_rows = snapshot.current[snapshot.current["source"] == "aq"]
    joined = stations.join(aq_rows.drop(columns=["source"]), on="aq_cell")
    bands = joined["us_aqi"].map(aqi_category)
    joined["aqi_category"] = bands.map(lambda b: b.name if b else "Unknown")
    joined["aqi_color"] = bands.map(lambda b: b.color if b else "#8a8a85")
    return joined


def station_daily_means(snapshot: Snapshot, station: pd.Series) -> list[float]:
    """Outdoor daily mean temperatures (degF) at this station's weather cell,
    oldest first -- the input to the thermal model's trailing mean."""
    if snapshot.daily.empty:
        return []
    rows = snapshot.daily[snapshot.daily["cell"] == station["wx_cell"]]
    return [v for v in rows.sort_values("date")["t_mean"] if pd.notna(v)]


def station_flood_series(snapshot: Snapshot, station: pd.Series) -> pd.DataFrame:
    """Daily river discharge (m3/s) at this station's flood cell, oldest first.

    Columns: date, river_discharge. Empty frame if the API returned nothing for
    this cell (e.g. no river GloFAS resolves within 5 km of a fully tidal reach).
    """
    if snapshot.flood.empty:
        return pd.DataFrame(columns=["date", "river_discharge"])
    rows = snapshot.flood[snapshot.flood["cell"] == station["fl_cell"]]
    return rows.sort_values("date")[["date", "river_discharge"]].reset_index(drop=True)


def station_precipitation_series(snapshot: Snapshot, station: pd.Series) -> pd.DataFrame:
    """Hourly precipitation (mm) at this station's weather cell, oldest first.

    Columns: time, precipitation_mm. This is the pluvial (rainfall-driven) flood
    signal -- see flood.py -- distinct from the Flood API's river discharge,
    which tracks a different flood mechanism entirely.
    """
    rows = snapshot.hourly[
        (snapshot.hourly["cell"] == station["wx_cell"])
        & (snapshot.hourly["metric"] == "precipitation")
    ]
    return (
        rows.sort_values("time")[["time", "value"]]
        .rename(columns={"value": "precipitation_mm"})
        .reset_index(drop=True)
    )