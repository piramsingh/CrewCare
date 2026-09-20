"""The top 5 highest health-risk stations, without Streamlit.

WHY THIS FILE EXISTS
--------------------
Everything needed to rank stations by health risk was already in the repo --
`indoor.py` for platform PM2.5, `thermal.py` for heat, `flood.py` for mould,
`risk.py` for the 1-5 level -- but the loop that runs them over all 496
stations lived inside `app.py`, wrapped in Streamlit's cache decorators. That
made the list unavailable to anything that is not a Streamlit app: a FastAPI
route, the WhatsApp service, a scheduled export, a React dashboard.

This module is that loop with the decorators removed. It imports pandas and
requests and nothing else from the outside, so it runs in any Python process,
and its `--export` writes JSON for consumers that are not Python at all.

WHAT "HIGHEST HEALTH RISK" MEANS HERE
-------------------------------------
The same ranking the dashboard shows, and it is a two-step sort for a reason:

    1. the 1-5 level, descending          -- risk.py, the maximum of three axes
    2. platform PM2.5, descending         -- the tie-break
    3. heat index, then name              -- the remaining tie-breaks

The level saturates. Dozens of enclosed stations sit at the same top level,
because the PM2.5 source term is identical at every enclosed station with the
same service level, so the level alone cannot order them and the reading has
to. `tied_at_top` in the payload says how many share that level, so a consumer
can say "five of 46" rather than implying these five are uniquely the worst.

NOT A CLINICAL INSTRUMENT
-------------------------
Every figure is modelled, not measured -- see METHODOLOGY.md. The ranking is a
planning prior for where to look first, not a basis for clearing or condemning
a station, and not medical advice for any individual.

USAGE
-----
    from conditions import top_health_risk
    rows = top_health_risk(limit=5)          # list of dicts, ready to render

    python conditions.py                     # print the list
    python conditions.py --json              # the same payload as JSON
    python conditions.py --export out.json   # write it for a non-Python frontend

The export is a snapshot of live conditions, so it is written with a
`generated_at` timestamp and is not tracked in git: a committed copy would be
stating an hour-old reading as if it were current. Regenerate it on a schedule
or at build time.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import complaints
import flood
import indoor
import openmeteo as om
import risk as risk_model
import thermal

DEFAULT_LIMIT = 5
DEFAULT_TTL_HOURS = 3.0

# The columns a consumer gets, in the order a list renders them.
FIELDS = (
    "rank", "station_id", "complex_id", "stop_name", "routes", "borough",
    "structure", "enclosed", "platforms", "lat", "lon", "level", "level_name",
    "driver", "pm25", "temp_f", "feels_f", "rh", "mould", "reports",
)


@dataclass(frozen=True)
class RiskList:
    """A ranked list plus the context needed to caption it honestly."""

    rows: list[dict]
    generated_at: datetime
    scored_stations: int
    top_level: int
    tied_at_top: int
    borough: str

    def as_payload(self) -> dict:
        return {
            "generated_at": self.generated_at.isoformat(),
            "borough": self.borough,
            "scored_stations": self.scored_stations,
            "top_level": self.top_level,
            "tied_at_top": self.tied_at_top,
            "note": (
                f"{self.tied_at_top} of {self.scored_stations} stations sit at "
                f"level {self.top_level}; platform PM2.5 breaks the tie. All "
                f"figures are modelled, not measured."
            ),
            "stations": self.rows,
        }


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_stations(
    borough: str | None = None,
    *,
    ttl_hours: float = DEFAULT_TTL_HOURS,
    stations: pd.DataFrame | None = None,
    snapshot: om.Snapshot | None = None,
) -> pd.DataFrame:
    """Run the four models over every station and return one row each.

    `borough` of None (or "All boroughs") scores the whole network. Pass
    `stations`/`snapshot` to reuse work already done; otherwise both are loaded
    here, and `openmeteo` serves the snapshot from its disk cache unless the TTL
    has expired.
    """
    stations = om.load_stations() if stations is None else stations
    if borough and borough != "All boroughs":
        stations = stations[stations["borough"] == borough]
    if snapshot is None:
        snapshot = om.fetch_snapshot(om.load_stations(), ttl_hours=ttl_hours)

    report_counts = complaints.counts_by_station()

    rows: list[dict] = []
    for _, station in stations.iterrows():
        values = om.station_current(snapshot, station)
        if values.get("temperature_2m") is None:
            # No weather for this grid cell: score nothing rather than score it
            # against defaults and let it rank.
            continue

        source = indoor.subway_delta_c(station)
        climate = thermal.station_climate(
            station,
            t_out_f=values.get("temperature_2m"),
            rh_out=values.get("relative_humidity_2m"),
            dewpoint_out_f=values.get("dew_point_2m"),
            pressure_hpa=values.get("surface_pressure"),
            daily_means_f=om.station_daily_means(snapshot, station),
        )
        platform_pm25 = indoor.platform_pm25(values.get(indoor.PM25_KEY), source.delta_c)
        enclosed = indoor.enclosure_for(station["structure"]).is_enclosed()
        flood_climate = flood.station_flood_climate(
            om.station_precipitation_series(snapshot, station),
            om.station_flood_series(snapshot, station),
            rh_in=climate.rh_in,
            enclosed=enclosed,
        )
        assessed = risk_model.station_risk(
            platform_pm25, climate.heat_index_in_f,
            flood_climate.mold.level, flood_climate.mold.description,
        )

        rows.append({
            "station_id": station["gtfs_stop_id"],
            "complex_id": station["complex_id"],
            "stop_name": station["stop_name"],
            "routes": station["daytime_routes"],
            "borough": station["borough"],
            "structure": station["structure"],
            "enclosed": enclosed,
            "lat": float(station["lat"]),
            "lon": float(station["lon"]),
            "level": assessed.level,
            "level_name": assessed.name,
            "driver": assessed.driver,
            "pm25": round(platform_pm25, 1) if platform_pm25 is not None else None,
            "temp_f": round(climate.t_in_f, 1),
            "feels_f": round(climate.heat_index_in_f, 1),
            "rh": round(climate.rh_in),
            "mould": flood_climate.mold.level,
            "reports": report_counts.get(station["gtfs_stop_id"], 0),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# The list
# ---------------------------------------------------------------------------


def rank_by_risk(scored: pd.DataFrame, *, per_complex: bool = True) -> pd.DataFrame:
    """Level first, then PM2.5, then heat index, then name.

    Name last so the order is stable across runs: without it, two stations
    identical on all three measures would swap places between calls and a list
    that is supposed to be a ranking would look like it was changing.

    `per_complex` collapses a station complex to its worst platform. The spine
    is one row per GTFS stop, so 34 St-Herald Sq is two rows -- the N Q R W
    platform and the B D F M one -- and a straight top five can spend two of
    its five places on the same station, which reads as a bug. Collapsing keeps
    the worst platform and records how many it stands for in `platforms`.

    It groups on `complex_id`, never on name: "86 St" is four different
    stations on four different lines, and they are not interchangeable.
    """
    ranked = scored.sort_values(
        ["level", "pm25", "feels_f", "stop_name"],
        ascending=[False, False, False, True],
        na_position="last",
    )
    if not per_complex or "complex_id" not in ranked.columns:
        return ranked

    sizes = scored.groupby("complex_id").size()
    ranked = ranked.drop_duplicates(subset="complex_id", keep="first").copy()
    ranked["platforms"] = ranked["complex_id"].map(sizes).astype(int)
    return ranked


def top_health_risk(
    limit: int = DEFAULT_LIMIT,
    borough: str | None = None,
    *,
    ttl_hours: float = DEFAULT_TTL_HOURS,
    scored: pd.DataFrame | None = None,
    per_complex: bool = True,
) -> list[dict]:
    """The `limit` highest-risk stations as plain dicts, rank 1 first."""
    return risk_list(
        limit, borough, ttl_hours=ttl_hours, scored=scored, per_complex=per_complex
    ).rows


def risk_list(
    limit: int = DEFAULT_LIMIT,
    borough: str | None = None,
    *,
    ttl_hours: float = DEFAULT_TTL_HOURS,
    scored: pd.DataFrame | None = None,
    per_complex: bool = True,
) -> RiskList:
    """The list plus the counts a caption needs."""
    if scored is None:
        scored = score_stations(borough, ttl_hours=ttl_hours)

    now = datetime.now(timezone.utc)
    if scored.empty:
        return RiskList([], now, 0, 0, 0, borough or "All boroughs")

    top_level = int(scored["level"].max())
    ranked = rank_by_risk(scored, per_complex=per_complex).head(limit)
    rows = [
        {
            "rank": position,
            **{key: _plain(row.get(key, 1 if key == "platforms" else None))
               for key in FIELDS if key != "rank"},
        }
        for position, (_, row) in enumerate(ranked.iterrows(), start=1)
    ]
    return RiskList(
        rows=rows,
        generated_at=now,
        scored_stations=int(len(scored)),
        top_level=top_level,
        tied_at_top=int((scored["level"] == top_level).sum()),
        borough=borough or "All boroughs",
    )


def _plain(value):
    """numpy scalars out, JSON-serialisable values in."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def format_list(result: RiskList) -> str:
    """The list as text, for a terminal or a log."""
    if not result.rows:
        return "No stations scored."

    lines = [
        f"Top {len(result.rows)} highest health-risk stations · {result.borough}",
        f"{result.scored_stations} scored · "
        f"{result.tied_at_top} tied at level {result.top_level} · "
        f"modelled {result.generated_at.astimezone():%b %d, %H:%M %Z}",
        "",
    ]
    for row in result.rows:
        pm25 = "n/a" if row["pm25"] is None else f"{row['pm25']:>5.1f} ug/m3"
        lines.append(
            f"{row['rank']}. {row['stop_name']:<26} {row['routes']:<10} "
            f"level {row['level']} {row['level_name']:<9} {pm25}  "
            f"feels {row['feels_f']:.0f}F  {row['reports']} report(s)"
        )
        platforms = row.get("platforms") or 1
        span = f" · worst of {platforms} platforms" if platforms > 1 else ""
        lines.append(
            f"   driven by {row['driver'].lower()} · {row['structure']}{span}"
        )
    return "\n".join(lines)


def export(path: Path | str, result: RiskList) -> Path:
    """Write the payload as JSON for a consumer that is not Python."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.as_payload(), indent=2))
    return path


# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Top N highest health-risk subway stations (modelled)."
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument(
        "--borough", default=None,
        help="Manhattan, Brooklyn, Queens, Bronx or Staten Island. "
             "Omit for the whole network.",
    )
    parser.add_argument("--ttl-hours", type=float, default=DEFAULT_TTL_HOURS)
    parser.add_argument(
        "--per-stop", action="store_true",
        help="rank GTFS stops, not station complexes (a complex can then take "
             "more than one place in the list)",
    )
    parser.add_argument("--json", action="store_true", help="print JSON instead")
    parser.add_argument("--export", metavar="PATH", help="write the JSON to PATH")
    args = parser.parse_args(argv)

    result = risk_list(
        args.limit, args.borough, ttl_hours=args.ttl_hours,
        per_complex=not args.per_stop,
    )

    if args.export:
        print(f"wrote {export(args.export, result)}")
    if args.json:
        print(json.dumps(result.as_payload(), indent=2))
    elif not args.export:
        print(format_list(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
