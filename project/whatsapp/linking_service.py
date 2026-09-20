"""
One-time-code account linking between an authenticated web session and a
WhatsApp number. See the flow described in the project spec, section 8.

Security properties enforced here:
- Codes expire (LINKING_CODE_TTL_MINUTES).
- Codes are single-use.
- Verification is rate-limited per code (MAX_ATTEMPTS).
- Only an already-authenticated employee_id can generate a code — a WhatsApp
  number alone never grants access to link to an arbitrary account.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from .models import LinkingCode, WhatsAppLink

MAX_ATTEMPTS = 5


class LinkingError(Exception):
    pass


def start_linking(db: Session, employee_id: str) -> LinkingCode:
    """Called from POST /api/whatsapp/linking/start, behind normal auth
    middleware — employee_id must come from the authenticated session, never
    from client-supplied input."""
    # Invalidate any previous unused codes for this employee first.
    db.query(LinkingCode).filter(
        LinkingCode.employee_id == employee_id,
        LinkingCode.used_at.is_(None),
    ).delete()

    code = LinkingCode.generate(employee_id)
    db.add(code)
    db.commit()
    db.refresh(code)
    return code


def verify_and_link(db: Session, code_value: str, whatsapp_number: str) -> WhatsAppLink:
    """Called from the webhook handler when an incoming message's text looks
    like a linking code. Raises LinkingError with a safe, user-facing reason
    on any failure."""
    record = (
        db.query(LinkingCode)
        .filter(LinkingCode.code == code_value)
        .one_or_none()
    )

    if record is None:
        raise LinkingError("That code wasn't recognized. Please check and try again.")

    if record.attempt_count >= MAX_ATTEMPTS:
        raise LinkingError("Too many attempts for this code. Please request a new one.")

    record.attempt_count += 1
    db.add(record)
    db.commit()

    if record.is_used:
        raise LinkingError("That code has already been used. Please request a new one.")

    if record.is_expired:
        raise LinkingError("That code has expired. Please request a new one from the app.")

    # Prevent linking the same WhatsApp number to more than one active account.
    existing = (
        db.query(WhatsAppLink)
        .filter(WhatsAppLink.whatsapp_number == whatsapp_number, WhatsAppLink.revoked_at.is_(None))
        .one_or_none()
    )
    if existing is not None and existing.employee_id != record.employee_id:
        raise LinkingError(
            "This WhatsApp number is already linked to a different account. "
            "Contact your administrator if this is unexpected."
        )

    link = existing or WhatsAppLink(employee_id=record.employee_id, whatsapp_number=whatsapp_number)
    record.used_at = datetime.utcnow()

    db.add(link)
    db.add(record)
    db.commit()
    db.refresh(link)
    return link


def unlink(db: Session, employee_id: str) -> None:
    link = (
        db.query(WhatsAppLink)
        .filter(WhatsAppLink.employee_id == employee_id, WhatsAppLink.revoked_at.is_(None))
        .one_or_none()
    )
    if link is not None:
        link.revoked_at = datetime.utcnow()
        db.add(link)
        db.commit()


def resolve_employee_id(db: Session, whatsapp_number: str) -> str | None:
    """Look up which employee a given incoming WhatsApp number belongs to.
    Returns None if unlinked — the webhook handler should then start the
    linking flow instead of any conversation state."""
    link = (
        db.query(WhatsAppLink)
        .filter(WhatsAppLink.whatsapp_number == whatsapp_number, WhatsAppLink.revoked_at.is_(None))
        .one_or_none()
    )
    return link.employee_id if link else None
