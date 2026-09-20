"""Checks for `conditions.py`. Run it directly:

    python test_conditions.py

Plain asserts and a printed report, no test framework, because the repo has no
test dependency and this needs to stay runnable from a bare checkout.

It hits Open-Meteo through `openmeteo.py`'s disk cache, so the first run makes
a handful of requests and later runs make none until the TTL expires. That is
deliberate: the thing worth checking is that the real pipeline agrees with the
dashboard, and a fixture of frozen readings would only prove the fixture.

The parity section imports `app.py` to compare against the dashboard's own
scoring loop. If Streamlit is not installed that section skips rather than
fails, so the module can be verified in a service environment that has no UI.
"""

from __future__ import annotations

import json
import sys

import pandas as pd

import conditions

_failures: list[str] = []
_skipped: list[str] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    print(f"{'PASS' if passed else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not passed:
        _failures.append(name)


def skip(name: str, why: str) -> None:
    print(f"SKIP  {name}  ({why})")
    _skipped.append(name)


def main() -> int:
    scored = conditions.score_stations()
    result = conditions.risk_list(5)

    # --- the list itself ---------------------------------------------------
    check("stations were scored", len(scored) > 0, f"{len(scored)} stations")
    check("five rows returned", len(result.rows) == 5)
    check("ranks are 1..5 in order",
          [row["rank"] for row in result.rows] == [1, 2, 3, 4, 5])
    check("every declared field is present",
          all(set(row) == set(conditions.FIELDS) for row in result.rows))

    levels = [row["level"] for row in result.rows]
    check("levels never increase down the list",
          levels == sorted(levels, reverse=True), str(levels))

    within = [row["pm25"] for row in result.rows if row["level"] == levels[0]]
    check("PM2.5 breaks ties within a level",
          within == sorted(within, reverse=True), str(within))

    check("tie context is reported",
          result.tied_at_top >= 1 and result.top_level == levels[0],
          f"{result.tied_at_top} tied at level {result.top_level}")
    check("the list is a subset of what was scored",
          result.scored_stations == len(scored))

    # --- payload, for a consumer that is not Python -------------------------
    payload = result.as_payload()
    try:
        round_tripped = json.loads(json.dumps(payload))
        clean = round_tripped == payload
    except TypeError as error:          # a numpy scalar would land here
        round_tripped, clean = None, False
        print(f"      json error: {error}")
    check("payload is JSON-serialisable and survives a round trip", clean)

    # --- arguments ----------------------------------------------------------
    borough = conditions.risk_list(3, "Brooklyn")
    check("borough scopes the pool",
          0 < borough.scored_stations < len(scored),
          f"{borough.scored_stations} in Brooklyn")
    check("borough rows are all from that borough",
          all(row["borough"] == "Brooklyn" for row in borough.rows))
    check("limit is honoured", len(borough.rows) == 3)

    complexes = [row["complex_id"] for row in result.rows]
    check("no station complex appears twice",
          len(set(complexes)) == len(complexes), str(complexes))
    check("platforms says how many stops each row stands for",
          all(isinstance(row["platforms"], int) and row["platforms"] >= 1
              for row in result.rows),
          str([row["platforms"] for row in result.rows]))

    multi = scored.groupby("complex_id").size()
    multi = multi[multi > 1]
    check("the spine really does have multi-platform complexes to collapse",
          len(multi) > 0, f"{len(multi)} complexes span more than one stop")

    per_stop_all = conditions.rank_by_risk(scored, per_complex=False)
    check("per-stop ranking keeps every scored row",
          len(per_stop_all) == len(scored), f"{len(per_stop_all)} rows")
    check("collapsed ranking keeps one row per complex",
          len(conditions.rank_by_risk(scored)) == scored["complex_id"].nunique())

    reused = conditions.risk_list(5, scored=scored)
    check("passing an existing frame gives the same list",
          [r["station_id"] for r in reused.rows]
          == [r["station_id"] for r in result.rows])

    # --- degenerate input ---------------------------------------------------
    empty = conditions.risk_list(5, scored=pd.DataFrame(columns=list(conditions.FIELDS)))
    check("an empty frame returns an empty list",
          empty.rows == [] and empty.scored_stations == 0)
    check("an empty list still formats",
          "No stations scored." in conditions.format_list(empty))

    # --- parity with the dashboard -----------------------------------------
    try:
        import app
    except ImportError as error:
        skip("scores match app.py station for station", f"no Streamlit: {error}")
        skip("top 5 matches the dashboard's own ranking", "no Streamlit")
    else:
        theirs = app.score_borough("All boroughs", 3.0, 0)
        mine = scored.set_index("station_id").sort_index()
        theirs = theirs.set_index("station_id").sort_index()
        columns = ["level", "pm25", "temp_f", "feels_f", "rh", "mould", "driver"]
        check("scores match app.py station for station",
              len(mine) == len(theirs)
              and all(mine[c].equals(theirs[c]) for c in columns),
              f"{len(mine)} stations, {len(columns)} columns")
        dashboard_order = (
            theirs.reset_index()
            .sort_values(["level", "pm25", "feels_f", "stop_name"],
                         ascending=[False, False, False, True], na_position="last")
            .head(5)["stop_name"].tolist()
        )
        per_stop = conditions.top_health_risk(5, scored=scored, per_complex=False)
        check("top 5 per stop matches the dashboard's own ranking",
              [row["stop_name"] for row in per_stop] == dashboard_order,
              ", ".join(dashboard_order))

    print()
    if _failures:
        print(f"{len(_failures)} FAILED: {', '.join(_failures)}")
    else:
        print(f"all checks passed{f' ({len(_skipped)} skipped)' if _skipped else ''}")
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
