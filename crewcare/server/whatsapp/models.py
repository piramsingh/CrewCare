"""
Database models for the WhatsApp integration.

These are intentionally minimal and additive: they assume a `WorkerAccount`
table already exists elsewhere in the app (from the auth/worker module) and
only reference it by `employee_id`. Wire the ForeignKey up to your real
User/WorkerProfile table when integrating.
"""
from datetime import datetime, timedelta
import enum
import secrets

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

LINKING_CODE_TTL_MINUTES = 10
LINKING_CODE_LENGTH = 6


class ConversationState(str, enum.Enum):
    START = "START"
    CONSENT = "CONSENT"
    BASIC_HEALTH = "BASIC_HEALTH"
    REPORT_OPTION = "REPORT_OPTION"
    REPORT_UPLOAD = "REPORT_UPLOAD"
    HEALTH_APP_OPTION = "HEALTH_APP_OPTION"
    ENVIRONMENTAL_SUMMARY = "ENVIRONMENTAL_SUMMARY"
    RECOMMENDATIONS = "RECOMMENDATIONS"
    CONCERN_REVIEW = "CONCERN_REVIEW"
    FREEFORM_QA = "FREEFORM_QA"
    COMPLETED = "COMPLETED"


class LinkingCode(Base):
    """A short-lived, single-use code a worker sends over WhatsApp to prove
    they control both the logged-in web session and the WhatsApp number."""

    __tablename__ = "linking_codes"

    id = Column(Integer, primary_key=True)
    employee_id = Column(String, nullable=False, index=True)
    code = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    attempt_count = Column(Integer, default=0, nullable=False)

    @classmethod
    def generate(cls, employee_id: str) -> "LinkingCode":
        # Numeric code -> easy to type on a phone keyboard.
        code = f"{secrets.randbelow(10**LINKING_CODE_LENGTH):0{LINKING_CODE_LENGTH}d}"
        return cls(
            employee_id=employee_id,
            code=code,
            expires_at=datetime.utcnow() + timedelta(minutes=LINKING_CODE_TTL_MINUTES),
        )

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None


class WhatsAppLink(Base):
    """A confirmed link between a WhatsApp number and an employee account."""

    __tablename__ = "whatsapp_links"
    __table_args__ = (UniqueConstraint("whatsapp_number", name="uq_whatsapp_number"),)

    id = Column(Integer, primary_key=True)
    employee_id = Column(String, nullable=False, index=True)
    # Store the normalized WhatsApp/E.164 number. Never log this value elsewhere.
    whatsapp_number = Column(String, nullable=False, index=True)
    linked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


class ConversationSession(Base):
    """Persisted per-worker conversation state so the flow can resume across
    separate incoming WhatsApp messages/webhook calls."""

    __tablename__ = "conversation_sessions"

    id = Column(Integer, primary_key=True)
    employee_id = Column(String, nullable=False, unique=True, index=True)
    state = Column(SAEnum(ConversationState), default=ConversationState.START, nullable=False)
    # Where the worker is in the CrewCare script (a step id from script.json),
    # and the answers so far as a JSON object. Used by conversation_adapter;
    # the legacy StationShield service uses `state` alone.
    step_id = Column(String, nullable=True)
    context_json = Column(Text, nullable=True)
    consent_given = Column(Boolean, default=False, nullable=False)
    health_sharing_opt_in = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ProcessedWebhookEvent(Base):
    """De-duplication record: Meta may redeliver the same webhook event on
    timeout/retry. Track message ids we've already handled."""

    __tablename__ = "processed_webhook_events"

    id = Column(Integer, primary_key=True)
    whatsapp_message_id = Column(String, nullable=False, unique=True, index=True)
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
