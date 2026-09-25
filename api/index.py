"""
The CrewCares operations API, as a Vercel serverless function.

This adds no science and no routes of its own: it reuses `crewcare/server`
exactly as it runs locally, and only fixes up the two things a serverless
host changes.

  1. The model package lives in `admin_dashboard/`, outside `crewcare/`, so
     ADMIN_MODEL_DIR points at it explicitly rather than relying on the
     bridge's relative search.
  2. The deployment directory is read-only. CREWCARE_STATE_DIR moves the
     model's Open-Meteo disk cache and its seeded complaint store to /tmp,
     the only writable path on the function. The bridge already supports
     this; nothing in the team's model code is edited.

Both are set with setdefault so a real environment variable still wins.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

os.environ.setdefault(
    "ADMIN_MODEL_DIR", str(ROOT / "admin_dashboard" / "admin_dashboard_model")
)
os.environ.setdefault("CREWCARE_STATE_DIR", "/tmp/crewcares")

sys.path.insert(0, str(ROOT / "crewcare" / "server"))

from main import app  # noqa: E402  — the FastAPI ASGI app Vercel serves
