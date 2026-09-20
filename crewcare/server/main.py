"""
CrewCare operations API.

Serves the dashboard's data and nothing else: a thin JSON layer over the
team's models in `admin_dashboard/admin_dashboard_model/`. The worker-facing
demo needs no server at all — it runs entirely in the browser.
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ops.api import router as ops_router

app = FastAPI(title="CrewCare")

# The web app runs on a different origin from this server, so the browser
# needs permission to call it.
#
# In development Vite picks whatever port is free, so pinning a list of ports
# just produces confusing CORS failures later. Any localhost port is allowed
# instead. For a deployment, set WEB_ORIGINS to the exact origins — the regex
# is then not used, because "any localhost" is not a rule you want in front of
# something reachable.
_configured = [o.strip() for o in os.environ.get("WEB_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_configured,
    allow_origin_regex=None if _configured else r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Content-Type"],
)

app.include_router(ops_router)


@app.get("/")
def health():
    return {"status": "ok"}
