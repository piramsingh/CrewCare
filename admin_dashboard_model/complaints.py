"""Anonymous worker complaints, stored per station.

ANONYMITY IS A STORAGE DECISION, NOT A UI LABEL
-----------------------------------------------
A record holds only: station id, the date (not the time), a category, a
severity and the free text. There is no worker id, no name, no device or
session identifier, and nothing is derived from the submitter. A record cannot
be linked back to a person by anything this module keeps.

Two deliberate choices beyond "don't store a name":

  DATE, NOT TIMESTAMP. A precise submission time plus a roster identifies who
  was on duty. Day-level granularity is enough to spot a pattern and coarse
  enough to break that link.

  NO EDIT OR DELETE BY SUBMITTER. Any "delete my own entry" feature needs a
  token tying a person to a record, which is exactly what we refuse to store.

The residual risk is the free text itself -- "I'm the only conductor on the
midnight A" identifies someone however little metadata we keep -- so the form
warns about it, and `SMALL_COUNT_THRESHOLD` drives a caution in the UI when a
station has so few reports that any one of them stands out.

THE SEEDED ENTRIES ARE SYNTHETIC. `seed_demo_complaints()` writes illustrative
records so a fresh install has something to show. They carry `demo: true` and
are labelled as such wherever they are displayed. They are not reports from
real workers and must not be read as evidence about any real station.
"""

from __future__ import annotations

import csv
import json
import random
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

APP_DIR = Path(__file__).resolve().parent
STORE = APP_DIR / "complaints.json"

# The published synthetic corpus. The runtime store above is deliberately
# untracked, so this is the tracked copy every consumer reads -- this app, and
# anything else in the repo that needs the same records.
CORPUS_CSV = APP_DIR.parent / "datasets" / "worker_complaints.csv"
CORPUS_FIELDS = (
    "id", "station_id", "days_ago", "reported_on", "category", "severity",
    "text", "demo",
)

# Below this many reports, a single one is identifiable enough to warrant a note.
SMALL_COUNT_THRESHOLD = 3

CATEGORIES: tuple[str, ...] = (
    "Dust or air quality",
    "Heat",
    "Damp, mould or standing water",
    "Ventilation or airflow",
    "Fumes or exhaust",
    "Noise",
    "Other",
)

SEVERITIES: tuple[str, ...] = (
    "Noticeable",
    "Affects my work",
    "Made me unwell",
)

# Which dashboard metric each category speaks to, so the UI can say whether the
# model agrees with what workers are reporting.
CATEGORY_METRIC: dict[str, str] = {
    "Dust or air quality": "pm25",
    "Fumes or exhaust": "pm25",
    "Heat": "heat",
    "Damp, mould or standing water": "humidity",
    "Ventilation or airflow": "heat",
}


@dataclass
class Complaint:
    """One anonymous report. Note the fields that are absent."""

    id: str
    station_id: str          # gtfs_stop_id
    reported_on: str         # ISO date, deliberately not a timestamp
    category: str
    severity: str
    text: str
    demo: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


def _read_raw() -> list[dict]:
    if not STORE.exists():
        return []
    try:
        payload = json.loads(STORE.read_text())
    except (OSError, ValueError):
        return []
    return payload if isinstance(payload, list) else []


def _write_raw(rows: list[dict]) -> None:
    # Write-then-rename so an interrupted write cannot truncate the store.
    temporary = STORE.with_suffix(".tmp")
    temporary.write_text(json.dumps(rows, indent=2))
    temporary.replace(STORE)


def load_all() -> list[Complaint]:
    out = []
    for row in _read_raw():
        try:
            out.append(Complaint(**row))
        except TypeError:
            continue  # a row from an older shape; skip rather than crash
    return out


def for_station(station_id: str) -> list[Complaint]:
    """Reports for one station, newest first."""
    rows = [c for c in load_all() if c.station_id == station_id]
    return sorted(rows, key=lambda c: c.reported_on, reverse=True)


def counts_by_station() -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in load_all():
        counts[c.station_id] = counts.get(c.station_id, 0) + 1
    return counts


def add(
    station_id: str, category: str, severity: str, text: str,
    reported_on: date | None = None,
) -> Complaint:
    """Append one report. Nothing about the submitter is recorded."""
    complaint = Complaint(
        id=uuid.uuid4().hex[:12],
        station_id=station_id,
        reported_on=(reported_on or date.today()).isoformat(),
        category=category,
        severity=severity,
        text=text.strip(),
        demo=False,
    )
    rows = _read_raw()
    rows.append(complaint.as_dict())
    _write_raw(rows)
    return complaint


def category_summary(complaints: list[Complaint]) -> list[tuple[str, int]]:
    """Categories present, most reported first."""
    counts: dict[str, int] = {}
    for c in complaints:
        counts[c.category] = counts.get(c.category, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


# ---------------------------------------------------------------------------
# Demo seed
# ---------------------------------------------------------------------------

_DEMO: tuple[tuple[str, str, str, str, int], ...] = (
    # (gtfs_stop_id, category, severity, text, days_ago)
    ("A02", "Damp, mould or standing water", "Made me unwell",
     "Persistent damp smell at the north end of the platform. Dark staining on "
     "the wall tiles that has not been cleaned in months.", 6),
    ("A02", "Dust or air quality", "Affects my work",
     "Black grit settles on every surface in the booth overnight. Wiping it down "
     "twice a shift and it comes straight back.", 19),
    ("A02", "Ventilation or airflow", "Noticeable",
     "Air feels completely still between trains on the overnight tour.", 27),
    ("127", "Heat", "Affects my work",
     "Platform is stifling by the end of the tour even with the street cool. "
     "No relief anywhere on the mezzanine.", 3),
    ("127", "Dust or air quality", "Affects my work",
     "Metallic taste in the mouth after a full tour on the platform.", 11),
    ("127", "Noise", "Noticeable",
     "Braking screech on the express track is painful without plugs.", 24),
    ("R16", "Heat", "Made me unwell",
     "Felt lightheaded near the end of shift. Had to sit down in the booth for "
     "twenty minutes before I could carry on.", 5),
    ("R16", "Dust or air quality", "Affects my work",
     "Visible haze along the platform during the evening peak.", 15),
    ("635", "Dust or air quality", "Made me unwell",
     "Coughing through the whole tour and for an hour after I get home. Worse on "
     "days I am on the platform rather than in the booth.", 8),
    ("635", "Ventilation or airflow", "Affects my work",
     "The fans at the south end have not run in weeks.", 21),
    ("L06", "Dust or air quality", "Noticeable",
     "Fine dust on the benches within an hour of cleaning.", 13),
    ("D17", "Fumes or exhaust", "Made me unwell",
     "Diesel work train sat in the station for close to an hour on the midnights. "
     "Eyes streaming, headache for the rest of the tour.", 9),
)


# The generated corpus below is sized so the dashboard has a network-scale
# picture to draw: ~425 reports across ~190 stations over the last twelve weeks,
# with a long tail of one-off reports and a short head of stations reported
# again and again. Every one of them is synthetic and carries `demo: true`.
CORPUS_WEEKS = 12
CORPUS_SHAPE: tuple[tuple[int, int, int], ...] = (
    # (stations, min reports, max reports) -- the head first
    (15, 5, 8),
    (40, 3, 4),
    (60, 2, 2),
    (75, 1, 1),
)

# Category mix, before the per-structure adjustment below.
_CATEGORY_WEIGHTS: dict[str, float] = {
    "Heat": 0.30,
    "Dust or air quality": 0.26,
    "Ventilation or airflow": 0.15,
    "Damp, mould or standing water": 0.13,
    "Fumes or exhaust": 0.08,
    "Noise": 0.05,
    "Other": 0.03,
}

# An enclosed platform traps heat and brake dust; an elevated one is open air
# and its complaints skew to weather, noise and the state of the structure.
_STRUCTURE_TILT: dict[str, dict[str, float]] = {
    "enclosed": {
        "Heat": 1.45, "Dust or air quality": 1.40,
        "Ventilation or airflow": 1.35, "Damp, mould or standing water": 1.25,
        "Fumes or exhaust": 1.15, "Noise": 0.55, "Other": 0.7,
    },
    "open": {
        "Heat": 0.55, "Dust or air quality": 0.50, "Ventilation or airflow": 0.25,
        "Damp, mould or standing water": 0.70, "Fumes or exhaust": 0.60,
        "Noise": 2.20, "Other": 1.60,
    },
}

_SEVERITY_WEIGHTS: dict[str, float] = {
    "Noticeable": 0.50,
    "Affects my work": 0.35,
    "Made me unwell": 0.15,
}

_WHERE: tuple[str, ...] = (
    "at the north end of the platform", "by the booth", "on the mezzanine",
    "at the south end", "near the stairs to the street", "along the express track",
    "in the crew room", "by the turnstiles",
)

_TEXT: dict[str, tuple[str, ...]] = {
    "Heat": (
        "Stifling {where} for most of the tour, no relief anywhere in the station.",
        "Had to step up to the street twice {where} just to cool down.",
        "Heat {where} is worse than the street by a long way, even after dark.",
        "No shade and no airflow {where}; the whole tour is spent in it.",
    ),
    "Dust or air quality": (
        "Black grit over every surface {where} within an hour of it being wiped.",
        "Visible haze {where} through the evening peak.",
        "Metallic taste in the mouth after a full tour {where}.",
        "Coughing through the tour and for an hour after I get home.",
    ),
    "Ventilation or airflow": (
        "Air is completely still between trains {where}.",
        "The fans {where} have not run for weeks.",
        "No noticeable airflow {where} at any point in the tour.",
    ),
    "Damp, mould or standing water": (
        "Persistent damp smell {where}, dark staining on the tiles.",
        "Water pooling {where} for days after the last rain.",
        "Mould visible on the wall {where}, nothing has been cleaned.",
        "Standing water on the floor {where} and the air is heavy with it.",
    ),
    "Fumes or exhaust": (
        "Diesel work train sat in the station close to an hour on the midnights.",
        "Exhaust smell {where} that lingers well after the equipment has gone.",
        "Fumes drifting down from the street vent {where}.",
    ),
    "Noise": (
        "Braking screech {where} is painful without plugs.",
        "Announcement speakers {where} distort loud enough to hurt.",
        "Constant structural rumble {where} through the whole tour.",
    ),
    "Other": (
        "Lighting {where} has been out for weeks, hard to see the platform edge.",
        "Rodents {where} through the overnight tour.",
        "Broken tiles and debris {where} that nobody has come to clear.",
    ),
}


def _station_pool() -> list[tuple[str, bool]]:
    """(gtfs_stop_id, enclosed) for every station in the spine.

    Read with the csv module rather than pandas: this module is imported by the
    store layer and has no business pulling a dataframe in to pick ids.
    """
    spine = APP_DIR.parent / "datasets" / "nyc_subway_station_spine.csv"
    if not spine.exists():
        return []
    with spine.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        (row["gtfs_stop_id"], row.get("structure", "") in ("Subway", "Open Cut"))
        for row in rows
        if row.get("gtfs_stop_id")
    ]


def _weighted(rng: random.Random, weights: dict[str, float]) -> str:
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys], k=1)[0]


def _generate_corpus(rng: random.Random, today: date) -> list[dict]:
    """The synthetic report corpus, deterministic for a given seed.

    Dates are drawn with a rising weight toward the present, so the trend line
    slopes the way a real reporting programme's does once word gets round --
    not because anything in the network changed.
    """
    pool = _station_pool()
    if not pool:
        return []

    anchors = {station_id for station_id, *_ in _DEMO}
    rng.shuffle(pool)
    # The handwritten anchor stations are excluded from the generated head so
    # their curated reports are not buried under filler.
    pool = [entry for entry in pool if entry[0] not in anchors]

    days = CORPUS_WEEKS * 7
    # Linearly rising recency weight: the newest week is ~3x the oldest.
    day_weights = [1.0 + 2.0 * (1 - index / days) for index in range(days)]

    rows: list[dict] = []
    cursor = 0
    for stations, low, high in CORPUS_SHAPE:
        for station_id, enclosed in pool[cursor:cursor + stations]:
            tilt = _STRUCTURE_TILT["enclosed" if enclosed else "open"]
            weights = {k: v * tilt[k] for k, v in _CATEGORY_WEIGHTS.items()}
            # A station's own reports must not repeat each other verbatim: a
            # duplicate line reads as a bug in the store, not as two workers
            # noticing the same thing.
            seen: set[str] = set()
            for _ in range(rng.randint(low, high)):
                category = _weighted(rng, weights)
                for _attempt in range(8):
                    text = rng.choice(_TEXT[category]).format(where=rng.choice(_WHERE))
                    if text not in seen:
                        break
                seen.add(text)
                days_ago = rng.choices(range(days), weights=day_weights, k=1)[0]
                rows.append(
                    Complaint(
                        id=uuid.uuid4().hex[:12],
                        station_id=station_id,
                        reported_on=(today - timedelta(days=days_ago)).isoformat(),
                        category=category,
                        severity=_weighted(rng, _SEVERITY_WEIGHTS),
                        text=text,
                        demo=True,
                    ).as_dict()
                )
        cursor += stations
    return rows


def load_corpus_csv(today: date | None = None) -> list[dict]:
    """The published corpus, with every date re-anchored to `today`.

    The CSV carries `days_ago` beside the ISO date for exactly this reason. A
    frozen date column would age: a month after the export, a dashboard showing
    "the last 30 days" would be empty, and the corpus exists to give it
    something to show. Re-anchoring keeps the shape of the twelve weeks --
    which station, which concern, how long ago -- and moves the window with the
    reader.
    """
    if not CORPUS_CSV.exists():
        return []
    today = today or date.today()
    rows: list[dict] = []
    with CORPUS_CSV.open(newline="") as handle:
        for record in csv.DictReader(handle):
            try:
                days_ago = int(record["days_ago"])
            except (KeyError, TypeError, ValueError):
                continue
            rows.append(
                Complaint(
                    id=record.get("id") or uuid.uuid4().hex[:12],
                    station_id=record["station_id"],
                    reported_on=(today - timedelta(days=days_ago)).isoformat(),
                    category=record["category"],
                    severity=record["severity"],
                    text=record["text"],
                    demo=True,
                ).as_dict()
            )
    return rows


def _generate_demo_rows(today: date) -> list[dict]:
    """The full demo set from the generator: handwritten anchors, then corpus."""
    rng = random.Random(20260919)
    anchors = [
        Complaint(
            id=uuid.uuid4().hex[:12],
            station_id=station_id,
            reported_on=(today - timedelta(days=days_ago)).isoformat(),
            category=category,
            severity=severity,
            text=text,
            demo=True,
        ).as_dict()
        for station_id, category, severity, text, days_ago in _DEMO
    ]
    return anchors + _generate_corpus(rng, today)


def _demo_rows(today: date | None = None) -> list[dict]:
    """The demo set: the published corpus if there is one, else a fresh draw.

    The CSV wins so that what this app shows and what anything else in the repo
    reads are the same records, rather than two independent draws from the same
    generator that happen to agree on the distribution and on nothing else.
    """
    today = today or date.today()
    return load_corpus_csv(today) or _generate_demo_rows(today)


def write_corpus_csv(path: Path | None = None, today: date | None = None) -> int:
    """Draw a fresh corpus and publish it as the tracked CSV. Returns the rows.

    Run this to change what the corpus contains; running the app does not, so a
    checkout always shows the records that are in version control.
    """
    path = path or CORPUS_CSV
    today = today or date.today()
    rows = _generate_demo_rows(today)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CORPUS_FIELDS))
        writer.writeheader()
        for row in sorted(rows, key=lambda r: r["reported_on"], reverse=True):
            reported = date.fromisoformat(row["reported_on"])
            writer.writerow({
                **row,
                "days_ago": (today - reported).days,
                "demo": "true",
            })
    return len(rows)


def seed_demo_complaints(force: bool = False) -> int:
    """Write the illustrative records. Returns how many were written.

    Real submissions are never touched. The demo rows are rewritten whenever
    their number no longer matches what the generator produces -- which is what
    upgrades a checkout seeded with the older twelve-record set -- and `force`
    rewrites them regardless.
    """
    existing = _read_raw()
    real = [row for row in existing if not row.get("demo")]
    demo = [row for row in existing if row.get("demo")]

    rows = _demo_rows()
    if demo and len(demo) == len(rows) and not force:
        return 0

    _write_raw(real + rows)
    return len(rows)


# ---------------------------------------------------------------------------
# Aggregates for the dashboard
# ---------------------------------------------------------------------------


def as_frame() -> "pd.DataFrame":
    """Every report as a frame, with `reported_on` parsed to a date."""
    import pandas as pd

    rows = [c.as_dict() for c in load_all()]
    frame = pd.DataFrame(rows, columns=[
        "id", "station_id", "reported_on", "category", "severity", "text", "demo",
    ])
    if frame.empty:
        return frame
    frame["reported_on"] = pd.to_datetime(frame["reported_on"], errors="coerce")
    return frame.dropna(subset=["reported_on"]).sort_values(
        "reported_on", ascending=False
    )


def weekly_counts(frame: "pd.DataFrame", weeks: int = CORPUS_WEEKS) -> "pd.DataFrame":
    """Reports per week, oldest first. Columns: week, reports."""
    import pandas as pd

    if frame.empty:
        return pd.DataFrame(columns=["week", "reports"])
    cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(weeks=weeks)
    window = frame[frame["reported_on"] >= cutoff]
    if window.empty:
        return pd.DataFrame(columns=["week", "reports"])
    counts = (
        window.set_index("reported_on")
        .resample("W-MON")
        .size()
        .rename("reports")
        .reset_index()
        .rename(columns={"reported_on": "week"})
    )
    # Both end buckets can be part-weeks -- the first is clipped by the window,
    # the last is still filling -- and a part-week plotted beside full ones reads
    # as a rise or a drop that has not happened.
    today = pd.Timestamp.today().normalize()
    counts = counts[counts["week"] <= today]
    if not counts.empty and counts["week"].iloc[0] - pd.Timedelta(days=7) < cutoff:
        counts = counts.iloc[1:]
    return counts.reset_index(drop=True)


def category_counts(frame: "pd.DataFrame") -> "pd.DataFrame":
    """Reports by concern type with their share. Columns: category, reports, share, label."""
    import pandas as pd

    if frame.empty:
        return pd.DataFrame(columns=["category", "reports", "share", "label"])
    counts = (
        frame.groupby("category").size().rename("reports").reset_index()
        .sort_values("reports", ascending=False)
    )
    total = counts["reports"].sum()
    counts["share"] = counts["reports"] / total * 100
    counts["label"] = counts["share"].map(lambda v: f"{v:.0f}%")
    return counts


def station_counts(frame: "pd.DataFrame") -> "pd.DataFrame":
    """Reports per station, most reported first. Columns: station_id, reports."""
    import pandas as pd

    if frame.empty:
        return pd.DataFrame(columns=["station_id", "reports"])
    return (
        frame.groupby("station_id").size().rename("reports").reset_index()
        .sort_values("reports", ascending=False)
    )


def recurring_station_ids(frame: "pd.DataFrame", minimum: int = 3) -> list[str]:
    """Stations reported `minimum` or more times -- a pattern, not an incident."""
    if frame.empty:
        return []
    counts = station_counts(frame)
    return list(counts[counts["reports"] >= minimum]["station_id"])


def period_change(frame: "pd.DataFrame", days: int = 30) -> tuple[int, int, float | None]:
    """(reports in the last `days`, reports in the `days` before that, % change)."""
    import pandas as pd

    if frame.empty:
        return 0, 0, None
    now = pd.Timestamp.today().normalize()
    recent = frame[frame["reported_on"] > now - pd.Timedelta(days=days)]
    prior = frame[
        (frame["reported_on"] <= now - pd.Timedelta(days=days))
        & (frame["reported_on"] > now - pd.Timedelta(days=2 * days))
    ]
    current, previous = len(recent), len(prior)
    if previous == 0:
        return current, previous, None
    return current, previous, (current - previous) / previous * 100


if __name__ == "__main__":  # pragma: no cover - a one-line maintenance command
    import sys

    if "--export" in sys.argv:
        written = write_corpus_csv()
        print(f"wrote {written} rows to {CORPUS_CSV}")
    else:
        print(__doc__)
        print(f"Usage: python complaints.py --export   # republish {CORPUS_CSV.name}")
