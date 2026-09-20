"""
Read-only JSON over the team's existing models.

The dashboard is React and the models are Python; this is the seam between
them. It calls `conditions.score_stations()` — the same function the Streamlit
app uses — and reshapes the result for the browser. It adds no science.

Two rules the endpoints keep:

  * Nothing is invented. A metric the models cannot produce comes back as
    null, and the UI renders "No data available" rather than a number.
  * Provenance travels with the data. Every figure is labelled live, modelled,
    derived or demo, so the interface can be honest about what it is showing
    without the front end having to guess.
"""
from __future__ import annotations

import math
import statistics
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from .model_bridge import ModelsUnavailable, load

router = APIRouter()

#: Windows the worker-report data can actually be filtered by. Environmental
#: readings are current-only and are never re-cut by these.
RANGE_DAYS: dict[str, int | None] = {
    "Live": None, "Today": 0, "7 Days": 7, "30 Days": 30, "60 Days": 60,
}


#: A route needs at least this many scored stations before its median means
#: anything. Below it, one station's reading is the whole bar.
MIN_STATIONS_PER_LINE = 5

#: How many bars the exposure chart has room for.
LINES_SHOWN = 6

#: NWS "Extreme Caution" begins here, which is where heat guidance starts.
HEAT_INDEX_CAUTION_F = 90.0

#: The card has room for three.
MAX_RECOMMENDATIONS = 3


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _exposure_by_line(stations: list[dict]) -> dict:
    """Median platform PM2.5 per route, as a multiple of the network median.

    This is a CONCENTRATION, not a dose: it says what the stations on a line
    are modelled at, not what a worker accumulates over a tour. Tour exposure
    would need a roster and tour lengths, which nothing in this repo has.
    """
    readings = [s["pm25"] for s in stations if s["pm25"] is not None]
    network = _median(readings)
    if not network:
        return {"networkMedian": None, "lines": []}

    per_route: dict[str, list[float]] = {}
    for station in stations:
        if station["pm25"] is None:
            continue
        for route in station["routes"]:
            per_route.setdefault(route, []).append(station["pm25"])

    lines = [
        {
            "line": route,
            "ratio": round(_median(values) / network, 2),
            "stations": len(values),
        }
        for route, values in per_route.items()
        if len(values) >= MIN_STATIONS_PER_LINE
    ]
    # Station count then name break the ties, so the bars keep a stable order
    # between refreshes instead of shuffling among equal ratios.
    lines.sort(key=lambda row: (-row["ratio"], -row["stations"], row["line"]))
    return {"networkMedian": round(network, 1), "lines": lines[:LINES_SHOWN]}


def _recommendations(stations: list[dict], reports: list[dict], days: int | None) -> list[dict]:
    """What to do first, derived from the same figures the screen is showing.

    Each entry is a query result phrased as an action. Nothing is generated
    prose, so nothing can claim something the data does not show. Rules are
    tried in priority order and the card takes the first three that fire;
    if none do, it keeps its empty state rather than inventing an item.
    """
    window = f"in the last {days} days" if days else "in this window"
    out: list[dict] = []

    # 1. Both signals at once: the model and the crew pointing at one platform.
    both = sorted(
        (s for s in stations if (s["level"] or 0) >= 4 and s["reports"] > 0),
        key=lambda s: (-s["reports"], -(s["pm25"] or 0)),
    )
    if both:
        worst = both[0]
        out.append({
            "id": "both-signals",
            "title": f"Rotate platform assignments at {worst['name']}",
            "detail": (
                f"Level {worst['level']} · {worst['pm25']:.0f} µg/m³ · "
                f"feels {worst['feelsF']:.0f}°F · {worst['reports']} report(s) {window}"
            ),
        })

    # 2. Heat, across the network rather than at one station.
    hot = [s for s in stations if (s["feelsF"] or 0) >= HEAT_INDEX_CAUTION_F]
    if hot:
        peak = max(hot, key=lambda s: s["feelsF"])
        out.append({
            "id": "heat",
            "title": f"Issue heat guidance on {len(hot)} platforms",
            "detail": (
                f"Feels-like ≥ {HEAT_INDEX_CAUTION_F:.0f}°F, peaking at "
                f"{peak['feelsF']:.0f}°F at {peak['name']} · NIOSH work/rest applies"
            ),
        })

    # 3. Severity, which decides who the report goes to.
    unwell = [r for r in reports if r.get("severity") == "Made me unwell"]
    if unwell:
        where = {str(r.get("station_id")) for r in unwell}
        out.append({
            "id": "severity",
            "title": f"Route {len(unwell)} reports to occupational health",
            "detail": (
                f"{len(where)} stations {window} · a clinical referral, not a "
                f"maintenance ticket"
            ),
        })

    # 4-5. Clusters of one concern at one station: a maintenance job, not a
    # rotation. These only surface when a rule above had nothing to say.
    for category, verb, note in (
        ("Ventilation or airflow", "Check the fans at", "ventilation report(s)"),
        ("Damp, mould or standing water", "Inspect", "damp report(s)"),
    ):
        if len(out) >= MAX_RECOMMENDATIONS:
            break
        counts: dict[str, int] = {}
        for report in reports:
            if report.get("category") == category:
                key = str(report.get("station_id"))
                counts[key] = counts.get(key, 0) + 1
        clustered = sorted(
            ((sid, n) for sid, n in counts.items() if n >= 2), key=lambda kv: -kv[1]
        )
        if not clustered:
            continue
        station_id, count = clustered[0]
        station = next((s for s in stations if s["id"] == station_id), None)
        if not station:
            continue
        humidity = f", platform humidity {station['humidity']:.0f}%" if station["humidity"] is not None else ""
        out.append({
            "id": f"cluster-{category}",
            "title": f"{verb} {station['name']}",
            "detail": f"{count} {note} {window} · level {station['level']}{humidity}",
        })

    return out[:MAX_RECOMMENDATIONS]


def _clean(value: Any) -> Any:
    """NaN and numpy scalars are not JSON. Missing stays missing."""
    if value is None:
        return None
    if isinstance(value, (str, bool)):
        return value
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
    except TypeError:
        pass
    item = getattr(value, "item", None)
    if callable(item):
        try:
            value = item()
        except Exception:
            return str(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _reports_within(models, days: int | None) -> list[dict]:
    """Complaints inside the window, newest first."""
    rows = []
    for complaint in models["complaints"].load_all():
        raw = {f: _clean(getattr(complaint, f, None)) for f in
               ("id", "station_id", "reported_on", "category", "severity", "text", "demo")}
        reported = raw.get("reported_on")
        if days is not None and reported:
            try:
                when = reported if isinstance(reported, date) else datetime.fromisoformat(str(reported)).date()
                if (date.today() - when).days > days:
                    continue
            except (TypeError, ValueError):
                pass
        if isinstance(raw.get("reported_on"), date):
            raw["reported_on"] = raw["reported_on"].isoformat()
        rows.append(raw)
    rows.sort(key=lambda r: str(r.get("reported_on") or ""), reverse=True)
    return rows


@router.get("/api/ops/snapshot")
def snapshot(range: str = Query("30 Days"), ttl_hours: float = 3.0) -> dict:
    """Everything the Overview needs, in one request.

    One call because the models compute the whole network at once anyway;
    splitting it would mean re-scoring 496 stations per panel.
    """
    try:
        models = load()
    except ModelsUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    days = RANGE_DAYS.get(range, 30)

    try:
        frame = models["conditions"].score_stations(ttl_hours=ttl_hours)
    except Exception as exc:
        # An upstream outage must not be papered over with numbers.
        raise HTTPException(
            status_code=503,
            detail=f"environmental data unavailable: {exc}",
        ) from exc

    reports = _reports_within(models, days)
    reports_by_station: dict[str, int] = {}
    for report in reports:
        key = str(report.get("station_id"))
        reports_by_station[key] = reports_by_station.get(key, 0) + 1

    stations = []
    for _, row in frame.iterrows():
        station_id = str(_clean(row.get("station_id")))
        stations.append({
            "id": station_id,
            "name": _clean(row.get("stop_name")),
            "routes": [r for r in str(_clean(row.get("routes")) or "").split() if r],
            "borough": _clean(row.get("borough")),
            "structure": _clean(row.get("structure")),
            "lat": _clean(row.get("lat")),
            "lon": _clean(row.get("lon")),
            "level": _clean(row.get("level")),
            "levelName": _clean(row.get("level_name")),
            "driver": _clean(row.get("driver")),
            "pm25": _clean(row.get("pm25")),
            "tempF": _clean(row.get("temp_f")),
            "feelsF": _clean(row.get("feels_f")),
            "humidity": _clean(row.get("rh")),
            "mould": _clean(row.get("mould")),
            "reports": reports_by_station.get(station_id, 0),
        })

    high_risk = [s for s in stations if (s["level"] or 0) >= 4]
    both_signals = [s for s in stations if (s["level"] or 0) >= 3 and s["reports"] > 0]

    counts: dict[str, int] = {}
    for report in reports:
        label = report.get("category") or "Other"
        counts[label] = counts.get(label, 0) + 1
    total = sum(counts.values())
    concerns = [
        {"label": label, "count": count,
         "percent": round(100 * count / total) if total else 0}
        for label, count in sorted(counts.items(), key=lambda kv: -kv[1])
    ]

    return {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "range": range,
        "rangeDays": days,
        "kpis": {
            "stationsMonitored": len(stations),
            "highRiskPlatforms": len(high_risk),
            "workerReports": len(reports),
            "bothSignals": len(both_signals),
        },
        "stations": stations,
        "concerns": concerns,
        "exposureByLine": _exposure_by_line(stations),
        "recommendations": _recommendations(stations, reports, days),
        "reportsAreDemo": all(r.get("demo") for r in reports) if reports else True,
        "provenance": {
            "outdoor": "live",      # Open-Meteo, no key, 3h disk cache
            "platform": "modelled", # indoor.py / thermal.py over the live reading
            "risk": "derived",      # risk.py bands over the modelled figures
            "reports": "demo",      # seeded corpus, not real MTA submissions
            "environmentalWindow": "current",
        },
    }


@router.get("/api/ops/station/{station_id}")
def station_detail(station_id: str, range: str = Query("30 Days")) -> dict:
    """One station, with its reports. Flood/mould come from the same models."""
    try:
        models = load()
    except ModelsUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    days = RANGE_DAYS.get(range, 30)
    reports = [r for r in _reports_within(models, days) if str(r.get("station_id")) == station_id]
    return {"stationId": station_id, "reports": reports}
