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
