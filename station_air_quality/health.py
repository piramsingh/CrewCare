"""Worker health-export upload: parsing, wearable "connect", notification prefs.

PROTOTYPE SCOPE
----------------
A worker uploads a health export (the demo fixture is a PDF shaped like an
iPhone Health export with a linked self-report). We pull out exactly three
things the rest of the app can use: the self-report Q&A, basic demographics,
and whatever field points at the worker's assigned station -- nothing else.
Per product direction, six-month trends, spirometry tables and similar extra
sections are deliberately left unparsed; they are noise for this prototype.

Parsing strategy: PDF text extraction does not preserve table layout, so
labels and their values can end up on the same line ("Subject ID CC-W1042")
or grouped by column ("Subject ID\\nAge band\\n...\\nCC-W1042\\n45-54\\n...").
Both shapes are handled the same way: find every occurrence of a known label
in the extracted text, sort those occurrences by position, and read each
field's value as whatever text sits between that label and the next one.

The "connect to Apple/Google Health" step and the notification preference are
both mocked: no network call is made and nothing is scheduled. They exist to
demonstrate the intended flow end-to-end and always report success.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

APP_DIR = Path(__file__).resolve().parent
STORE = APP_DIR / "health_uploads.json"

NOTIFICATION_CHOICES: tuple[str, ...] = (
    "Daily summary",
    "Significant changes only",
    "No updates",
)

WEARABLE_PROVIDERS: tuple[str, ...] = ("Apple Health", "Google Fit / Health Connect")

# label -> the literal phrases that introduce it in the export. Each is
# distinctive enough (multi-word, or a word not used as a label elsewhere)
# that one label's text can't be mistaken for the start of another.
_DEMOGRAPHIC_LABELS: dict[str, tuple[str, ...]] = {
    "subject_id": ("Subject ID", "Employee ID", "Worker ID"),
    "age_band": ("Age band", "Age range"),
    "sex": ("Sex", "Gender"),
    "height": ("Height",),
    "weight": ("Weight",),
    "occupation": ("Occupation", "Job title"),
    "division": ("Division",),
    "assigned_line": ("Assigned line",),
    "tour": ("Tour", "Shift"),
    "regular_days_off": ("Regular days off",),
    "home_terminal": ("Home terminal", "Assigned station"),
}

# Height/weight get a tight override: the generic label-to-next-label capture
# sits between them and the next known label.
_NUMERIC_OVERRIDES: tuple[tuple[str, re.Pattern], ...] = (
    ("height", re.compile(r"\bHeight\b\s*[:\-]?\s*([\d.]+\s*(?:cm|in|ft|m))\b", re.IGNORECASE)),
    ("weight", re.compile(r"\bWeight\b\s*[:\-]?\s*([\d.]+\s*(?:kg|lb|lbs))\b", re.IGNORECASE)),
)

# Self-report rows look like "3 What is the ...? I have high asthma ...".
# Bounded to a short prefix of the document -- the self-report and
# demographics sit near the top; multi-page daily-metric tables do not.
_SELF_REPORT_WINDOW = 4000
_QA_RE = re.compile(
    r"\b(\d{1,2})[\.\)]?\s+([^\n?]{3,240}\?)\s+(.*?)"
    r"(?=\s*\b\d{1,2}[\.\)]?\s+[^\n?]{3,240}\?|\Z)",
    re.DOTALL,
)


@dataclass
class HealthUpload:
    id: str
    uploaded_at: str
    source_filename: str
    demographics: dict
    self_report: list[dict]
    matched_station_id: str | None
    matched_station_label: str | None
    wearable_connected: bool = False
    wearable_provider: str | None = None
    notification_pref: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------


def extract_text(raw: bytes, filename: str) -> str:
    """Best-effort text from an uploaded file. PDF or plain text."""
    if filename.lower().endswith(".pdf"):
        from pypdf import PdfReader
        import io

        reader = PdfReader(io.BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return raw.decode("utf-8", errors="ignore")


# ---------------------------------------------------------------------------
# Demographics + self-report
# ---------------------------------------------------------------------------


def _label_matches(text: str) -> list[tuple[int, int, str]]:
    matches = []
    for key, variants in _DEMOGRAPHIC_LABELS.items():
        for variant in variants:
            pattern = re.compile(r"\b" + re.escape(variant) + r"\b", re.IGNORECASE)
            matches.extend((m.start(), m.end(), key) for m in pattern.finditer(text))
    matches.sort(key=lambda triple: triple[0])

    # Drop matches that overlap an earlier, already-claimed span.
    cleaned: list[tuple[int, int, str]] = []
    claimed_until = -1
    for start, end, key in matches:
        if start < claimed_until:
            continue
        cleaned.append((start, end, key))
        claimed_until = end
    return cleaned


def parse_demographics(text: str) -> dict:
    matches = _label_matches(text)
    fields: dict[str, str] = {}
    for i, (_, end, key) in enumerate(matches):
        value_end = matches[i + 1][0] if i + 1 < len(matches) else len(text)
        value = text[end:value_end]
        value = re.split(r"\n\s*\n", value, maxsplit=1)[0]  # stop at a blank line
        value = " ".join(value.split())
        if value and key not in fields:
            fields[key] = value

    for key, pattern in _NUMERIC_OVERRIDES:
        match = pattern.search(text)
        if match:
            fields[key] = match.group(1).strip()

    return fields


def parse_self_report(text: str) -> list[dict]:
    window = text[:_SELF_REPORT_WINDOW]
    rows = []
    for match in _QA_RE.finditer(window):
        question = match.group(2).strip()
        answer = " ".join(match.group(3).split())
        if answer:
            rows.append({"question": question, "answer": answer})
    return rows


# ---------------------------------------------------------------------------
# Station matching
# ---------------------------------------------------------------------------


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", value.lower()).strip()


def match_station(home_terminal: str | None, stations: pd.DataFrame) -> pd.Series | None:
    """Best-guess station for a free-text field like "207 St".

    Exact name match wins; otherwise a prefix/substring match, breaking ties
    towards the shorter (more literal) station name. Always a suggestion for
    the worker to confirm, never applied silently.
    """
    if not home_terminal:
        return None
    target = _normalize(home_terminal)
    if not target:
        return None

    best_row, best_score = None, -1.0
    for _, row in stations.iterrows():
        candidate = _normalize(row["stop_name"])
        if not candidate:
            continue
        if candidate == target:
            score = 100.0
        elif candidate.startswith(target) or target.startswith(candidate):
            score = 80.0
        elif target in candidate or candidate in target:
            score = 60.0
        else:
            continue
        score -= len(candidate) * 0.01  # tie-break towards the shorter name
        if score > best_score:
            best_score, best_row = score, row
    return best_row


# ---------------------------------------------------------------------------
# Wearable "connect" (mocked -- no network call, always succeeds)
# ---------------------------------------------------------------------------


def mock_connect_wearable(provider: str) -> dict:
    """Prototype only. Contacts nothing; always reports success."""
    return {
        "provider": provider,
        "connected": True,
        "connected_at": datetime.now().isoformat(timespec="seconds"),
        "message": f"Connected to {provider} (demo -- no data was actually transferred).",
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def _read_raw() -> list[dict]:
    if not STORE.exists():
        return []
    try:
        payload = json.loads(STORE.read_text())
    except (OSError, ValueError):
        return []
    return payload if isinstance(payload, list) else []


def _write_raw(rows: list[dict]) -> None:
    temporary = STORE.with_suffix(".tmp")
    temporary.write_text(json.dumps(rows, indent=2))
    temporary.replace(STORE)


def save_upload(upload: HealthUpload) -> None:
    rows = _read_raw()
    rows.append(upload.as_dict())
    _write_raw(rows)


def new_upload(
    source_filename: str,
    demographics: dict,
    self_report: list[dict],
    matched_station: pd.Series | None,
) -> HealthUpload:
    return HealthUpload(
        id=uuid.uuid4().hex[:12],
        uploaded_at=datetime.now().isoformat(timespec="seconds"),
        source_filename=source_filename,
        demographics=demographics,
        self_report=self_report,
        matched_station_id=str(matched_station["gtfs_stop_id"]) if matched_station is not None else None,
        matched_station_label=str(matched_station["label"]) if matched_station is not None else None,
    )
