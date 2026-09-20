"""
FastAPI router for:
  GET  /api/webhooks/whatsapp        - Meta webhook verification handshake
  POST /api/webhooks/whatsapp        - incoming message events
  POST /api/whatsapp/linking/start   - authenticated worker requests a code
  POST /api/whatsapp/unlink          - authenticated worker revokes their link

Mount with: app.include_router(router)
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from . import linking_service
from .conversation_adapter import handle_incoming_message
from .models import ProcessedWebhookEvent
from .whatsapp_client import get_whatsapp_client

# Replace with your real dependency-injected session + auth dependencies.
from .db import get_db  # noqa: F401  (placeholder import, see db.py)
from .auth import get_current_employee_id  # noqa: F401 (placeholder, see auth.py)

logger = logging.getLogger("whatsapp_webhook")
router = APIRouter()

WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET", "")  # for X-Hub-Signature-256 checks


@router.get("/api/webhooks/whatsapp")
async def verify_webhook(request: Request):
    """Meta's one-time handshake when you configure the callback URL."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN and WHATSAPP_VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")

    raise HTTPException(status_code=403, detail="Webhook verification failed")


def _verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Validates Meta's X-Hub-Signature-256 header against the app secret.
    Skips validation (with a warning) if no app secret is configured, so the
    demo still runs without it — do not skip this in a real deployment."""
    if not WHATSAPP_APP_SECRET:
        logger.warning("WHATSAPP_APP_SECRET not set; skipping signature verification (demo only).")
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(WHATSAPP_APP_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, provided)


@router.post("/api/webhooks/whatsapp")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    if not _verify_signature(raw_body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = await request.json()

    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]["value"]
    except (KeyError, IndexError):
        # Not a message event (e.g. a status update) — acknowledge and ignore.
        return {"status": "ignored"}

    messages = change.get("messages")
    if not messages:
        return {"status": "ignored"}

    for message in messages:
        message_id = message.get("id")
        if message_id and _already_processed(db, message_id):
            continue  # Meta redelivery — skip duplicate processing.

        from_number = message.get("from")  # E.164-ish, no leading '+'
        text_body = (message.get("text") or {}).get("body", "")

        await _process_single_message(db, from_number, text_body)

        if message_id:
            db.add(ProcessedWebhookEvent(whatsapp_message_id=message_id))
            db.commit()

    return {"status": "ok"}


async def _process_single_message(db: Session, from_number: str, text_body: str) -> None:
    client = get_whatsapp_client()

    employee_id = linking_service.resolve_employee_id(db, from_number)

    if employee_id is None:
        # Unlinked number: only accept a linking code, nothing else.
        code_candidate = text_body.strip()
        try:
            linking_service.verify_and_link(db, code_candidate, from_number)
            await client.send_text_message(
                from_number,
                "Your WhatsApp is now linked to CrewCare. Reply START to begin.",
            )
        except linking_service.LinkingError as exc:
            await client.send_text_message(
                from_number,
                f"{exc} If you haven't already, sign in to CrewCare and tap "
                "'Link my phone' to get a code.",
            )
        return

    # Linked: run the conversation state machine.
    # In a real build, fetch this worker's real station data here.
    station_context = _get_station_context_stub(employee_id)
    reply = handle_incoming_message(db, employee_id, text_body, station_context)
    await client.send_text_message(from_number, reply)


def _already_processed(db: Session, whatsapp_message_id: str) -> bool:
    return (
        db.query(ProcessedWebhookEvent)
        .filter_by(whatsapp_message_id=whatsapp_message_id)
        .one_or_none()
        is not None
    )


def _get_station_context_stub(employee_id: str) -> dict:
    """Placeholder — replace with a real lookup against your Station /
    StationEnvironmentalReading / EnvironmentalAssessment tables."""
    return {
        "station_name": "Synthetic Station A",
        "temperature_c": 24.5,
        "relative_humidity_percent": 78,
        "flood_exposure_status": "recent_exposure",
        "concern_level": "moderate",
        "source": "synthetic demo data",
        "timestamp": "2026-09-19T09:00:00Z",
    }


# --- Linking endpoints (called from the authenticated web app) ---


@router.post("/api/whatsapp/linking/start")
async def start_linking(
    db: Session = Depends(get_db),
    employee_id: str = Depends(get_current_employee_id),
):
    code = linking_service.start_linking(db, employee_id)
    return {
        "code": code.code,
        "expires_at": code.expires_at.isoformat(),
        "instructions": "Text this code to the CrewCare WhatsApp number to link your phone.",
    }


@router.post("/api/whatsapp/unlink")
async def unlink(
    db: Session = Depends(get_db),
    employee_id: str = Depends(get_current_employee_id),
):
    linking_service.unlink(db, employee_id)
    return {"status": "unlinked"}
