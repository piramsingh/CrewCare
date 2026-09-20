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

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
STORE = APP_DIR / "complaints.json"

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


def seed_demo_complaints(force: bool = False) -> int:
    """Write the illustrative records. Returns how many were written.

    Existing records are left alone unless `force`, so a real submission is
    never overwritten by a reseed.
    """
    existing = _read_raw()
    if existing and not force:
        return 0

    today = date.today()
    rows = [
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
    keep = [r for r in existing if not r.get("demo")] if force else []
    _write_raw(keep + rows)
    return len(rows)
