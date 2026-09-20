"""
Bridges the webhook to the CrewCare conversation.

`conversation_service.py` (the original StationShield state machine) is left
in place but no longer wired in: it and `crewcare_flow.py` are two designs of
the same conversation, and running both would guarantee they drift. This
module is the single seam — point it back at the old service by flipping the
import below if that flow is wanted instead.

Two columns were added to `ConversationSession` for this: `step_id` (where
the worker is in the script) and `context_json` (the answers so far). Both
are nullable, so the legacy service still works off `state` alone.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from .crewcare_flow import CrewCareFlow
from .models import ConversationSession, ConversationState

_flow = CrewCareFlow()


def _load(db: Session, employee_id: str) -> ConversationSession:
    session = db.query(ConversationSession).filter_by(employee_id=employee_id).one_or_none()
    if session is None:
        session = ConversationSession(employee_id=employee_id, state=ConversationState.START)
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


def _answers(session: ConversationSession) -> dict[str, str]:
    raw = getattr(session, "context_json", None)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {}


def handle_incoming_message(
    db: Session,
    employee_id: str,
    message_text: str,
    station_context: dict | None = None,
) -> str:
    """Advance the conversation one message and return the reply text.

    Returns a single string because that is what the webhook sends; the flow
    produces several bubbles, joined with blank lines so the shape of the
    scripted conversation survives the channel.
    """
    session = _load(db, employee_id)
    answers = _answers(session)

    step_id = session.step_id if getattr(session, "step_id", None) else None
    if step_id is None and not answers:
        reply = _flow.start()
    else:
        reply = _flow.advance(step_id, message_text, answers)

    session.step_id = reply.step_id
    session.context_json = json.dumps(answers)
    if reply.finished:
        session.state = ConversationState.COMPLETED
    db.add(session)
    db.commit()

    return "\n\n".join(m for m in reply.messages if m)
