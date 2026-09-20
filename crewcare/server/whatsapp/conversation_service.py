"""
State machine for the worker-facing WhatsApp conversation. Deterministic and
scripted, except for the FREEFORM_QA branch which delegates to ai_client.

This module returns plain strings (the reply text) so it can be driven
identically by the real webhook handler and the in-app WhatsApp mock/
simulator described in the spec (section 18) — same backend logic, two UIs.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from .models import ConversationSession, ConversationState
from .ai_client import get_ai_reply

CONSENT_TEXT = (
    "Before continuing, here's what optional health-data sharing means:\n\n"
    "- What: symptoms you choose to report, an optional health report, or an optional "
    "connection to a health app.\n"
    "- Why: to help identify if a work-location review may be needed.\n"
    "- Voluntary: yes — you can skip any part of this.\n"
    "- Who sees it: only authorized reviewers, never your full report by default.\n"
    "- Storage: kept securely and only as long as needed for this purpose.\n"
    "- Withdraw anytime: reply STOP DATA to withdraw consent, or ask for a human reviewer "
    "at any point.\n\n"
    "Reply YES to continue with the optional questionnaire, or SKIP to go straight to your "
    "station's environmental summary."
)

GREETING_TEXT = (
    "Hello! I'm StationShield, your environmental safety assistant.\n\n"
    "I can help you review your station's environmental conditions and safety guidance. "
    "Some parts of this chat are optional and involve sharing information about your health "
    "— you're always in control of that.\n\n"
    "Reply START to begin, INFO to learn more about how your data is used, or STOP to exit."
)


def _get_or_create_session(db: Session, employee_id: str) -> ConversationSession:
    session = db.query(ConversationSession).filter_by(employee_id=employee_id).one_or_none()
    if session is None:
        session = ConversationSession(employee_id=employee_id, state=ConversationState.START)
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


def handle_incoming_message(
    db: Session,
    employee_id: str,
    message_text: str,
    station_context: dict | None = None,
) -> str:
    """Core entry point: given the linked employee and their raw message
    text, advance conversation state and return the reply to send back."""
    session = _get_or_create_session(db, employee_id)
    text = (message_text or "").strip().lower()

    if text in ("stop", "exit", "cancel"):
        session.state = ConversationState.COMPLETED
        db.add(session)
        db.commit()
        return "Okay, ending this session. Message START anytime to begin again."

    if text == "stop data":
        session.consent_given = False
        session.health_sharing_opt_in = False
        db.add(session)
        db.commit()
        return (
            "Your consent for optional health-data sharing has been withdrawn. "
            "You can still access your station's environmental summary and guidance."
        )

    state = session.state

    if state == ConversationState.START:
        if text in ("start", "hi", "hello", "menu"):
            session.state = ConversationState.CONSENT
            reply = CONSENT_TEXT
        elif text == "info":
            reply = CONSENT_TEXT
        else:
            reply = GREETING_TEXT

    elif state == ConversationState.CONSENT:
        if text == "yes":
            session.consent_given = True
            session.state = ConversationState.BASIC_HEALTH
            reply = (
                "Thanks. This is optional — reply SKIP to any question.\n\n"
                "1) Are you currently experiencing any symptoms you'd like to report? "
                "(Reply with details, or SKIP)"
            )
        elif text == "skip":
            session.consent_given = False
            session.state = ConversationState.ENVIRONMENTAL_SUMMARY
            reply = _environmental_summary_text(station_context)
        else:
            reply = "Please reply YES to continue with the optional questionnaire, or SKIP."

    elif state == ConversationState.BASIC_HEALTH:
        # In a real build: store the free-text answer as a HealthDataField
        # tied to this employee, behind the same access controls as reports.
        session.state = ConversationState.REPORT_OPTION
        reply = (
            "Got it, thank you.\n\n"
            "Would you like to share a recent health report? Reply UPLOAD, INFO, or SKIP."
        )

    elif state == ConversationState.REPORT_OPTION:
        if text == "upload":
            session.state = ConversationState.REPORT_UPLOAD
            reply = (
                "Please send the report as a photo or PDF. Supported: JPG, PNG, PDF, under 10MB. "
                "It will be reviewed before anything is stored, and is not shared with your "
                "administrator by default."
            )
        elif text == "info":
            reply = (
                "Reports are stored securely, access-restricted, and used only to identify "
                "whether a work-location review may be warranted. Not every document type can "
                "be accurately interpreted automatically — a human reviews extracted fields "
                "before anything is finalized.\n\nReply UPLOAD or SKIP."
            )
        else:
            session.state = ConversationState.HEALTH_APP_OPTION
            reply = (
                "No problem. Would you like to learn about connecting an authorized health app? "
                "(This demo uses a simulated connection, not real Apple Health data.) "
                "Reply LEARN or SKIP."
            )

    elif state == ConversationState.REPORT_UPLOAD:
        # Real build: this branch is reached after media arrives via webhook;
        # route to secure temp storage + extraction-with-review, not shown here.
        session.state = ConversationState.HEALTH_APP_OPTION
        reply = (
            "Received — it will go through review before anything is stored. "
            "Would you like to learn about connecting an authorized health app? "
            "Reply LEARN or SKIP."
        )

    elif state == ConversationState.HEALTH_APP_OPTION:
        session.state = ConversationState.ENVIRONMENTAL_SUMMARY
        if text == "learn":
            reply = (
                "Apple Health data can only be accessed through a companion iOS app using "
                "HealthKit permissions — not directly through WhatsApp. In this demo, that "
                "connection is simulated with sample data, clearly labeled as such.\n\n"
                + _environmental_summary_text(station_context)
            )
        else:
            reply = _environmental_summary_text(station_context)

    elif state == ConversationState.ENVIRONMENTAL_SUMMARY:
        session.state = ConversationState.RECOMMENDATIONS
        reply = _recommendations_text(station_context)

    elif state == ConversationState.RECOMMENDATIONS:
        if text in ("concern", "raise concern", "report concern"):
            session.state = ConversationState.CONCERN_REVIEW
            reply = "Please describe your concern. It will be logged for human review, not an automated decision."
        elif text in ("ask", "question"):
            session.state = ConversationState.FREEFORM_QA
            reply = "Sure — what would you like to ask about your station or conditions?"
        else:
            session.state = ConversationState.COMPLETED
            reply = "You're all set. Reply MENU anytime to start again, RAISE CONCERN to report an issue, or ASK to ask a question."

    elif state == ConversationState.CONCERN_REVIEW:
        # Real build: create a WorkerConcern row here, notify admin queue.
        session.state = ConversationState.COMPLETED
        reply = (
            "Thank you — your concern has been logged for review by an authorized reviewer. "
            "This is not an automated decision. You'll be contacted through the usual "
            "workplace channel."
        )

    elif state == ConversationState.FREEFORM_QA:
        reply = get_ai_reply(message_text, station_context)
        session.state = ConversationState.COMPLETED

    else:  # COMPLETED or unknown
        session.state = ConversationState.START
        reply = GREETING_TEXT

    db.add(session)
    db.commit()
    return reply


def _environmental_summary_text(station_context: dict | None) -> str:
    if not station_context:
        return (
            "Environmental summary: data unavailable for your assigned station right now. "
            "Reply MENU to try again later."
        )
    lines = [f"Environmental summary for {station_context.get('station_name', 'your station')}:"]
    for label, key in [
        ("Temperature", "temperature_c"),
        ("Humidity", "relative_humidity_percent"),
        ("Flood exposure", "flood_exposure_status"),
        ("Concern level", "concern_level"),
    ]:
        value = station_context.get(key, "Data unavailable")
        lines.append(f"- {label}: {value}")
    lines.append(f"(Source: {station_context.get('source', 'demo data')}, as of {station_context.get('timestamp', 'unknown time')})")
    return "\n".join(lines)


def _recommendations_text(station_context: dict | None) -> str:
    concern = (station_context or {}).get("concern_level", "insufficient data")
    return (
        f"Guidance: environmental concern is currently classified as '{concern}' for your "
        "station in this demo. Follow applicable workplace procedures and required protective "
        "equipment guidance. If you have health concerns or symptoms, contact your supervisor "
        "or occupational health team.\n\n"
        "Reply RAISE CONCERN to report an issue, ASK to ask a question, or MENU for options."
    )
