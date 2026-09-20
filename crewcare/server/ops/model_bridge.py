"""
Locates and loads the team's existing model package, unchanged.

`admin_dashboard_model/` is a Streamlit app whose modules are pure functions
with no Streamlit dependency at import time — `openmeteo`, `indoor`,
`thermal`, `flood`, `risk`, `conditions`, `complaints`. This module puts that
directory on the path and re-exports them, so the API layer calls the real
models rather than reimplementing any of them.

Nothing here computes an environmental value. If the models cannot load, the
API says so; it never substitutes a plausible-looking number.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

#: Candidate locations, newest layout first.
#:
#: The model package has moved once already — from `admin_dashboard_model/` at
#: the repo root to `admin_dashboard/admin_dashboard_model/` — so this looks in
#: both rather than pinning one. ADMIN_MODEL_DIR overrides for other checkouts.
_RELATIVE = (
    Path("admin_dashboard") / "admin_dashboard_model",
    Path("admin_dashboard_model"),
)

CANDIDATES = [
    Path(os.environ["ADMIN_MODEL_DIR"]) if os.environ.get("ADMIN_MODEL_DIR") else None,
    *(root / rel for root in (HERE.parents[2], HERE.parents[3]) for rel in _RELATIVE),
]


class ModelsUnavailable(RuntimeError):
    """The model package could not be found or imported."""


def model_dir() -> Path:
    for candidate in CANDIDATES:
        if candidate and (candidate / "conditions.py").exists():
            return candidate
    raise ModelsUnavailable(
        "admin_dashboard_model/ not found. Set ADMIN_MODEL_DIR to its path — "
        f"looked in: {[str(c) for c in CANDIDATES if c]}"
    )


_loaded = None


def load():
    """Import the model modules once and hand them back."""
    global _loaded
    if _loaded is not None:
        return _loaded

    directory = model_dir()
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

    try:
        import complaints, conditions, flood, openmeteo, risk  # noqa: E402
    except Exception as exc:  # pragma: no cover - surfaced through the API
        raise ModelsUnavailable(f"could not import the models: {exc}") from exc

    # A fresh checkout has no complaints.json — it is gitignored so real
    # submissions never reach a public repo, and the app reseeds the
    # illustrative corpus on first run. The Streamlit app does this; without
    # it the API would report zero worker reports on a clean clone.
    try:
        complaints.seed_demo_complaints()
    except Exception:  # pragma: no cover - reports simply stay empty
        pass

    _loaded = {
        "dir": directory,
        "complaints": complaints,
        "conditions": conditions,
        "flood": flood,
        "openmeteo": openmeteo,
        "risk": risk,
    }
    return _loaded
