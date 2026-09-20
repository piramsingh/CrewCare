"""
Thin client around the WhatsApp Business Cloud API (Graph API).

Only implements what this MVP needs: sending text messages. Extend with
template messages / media messages if the demo requires them.
"""
from __future__ import annotations

import os
import logging
from typing import Any

import httpx

logger = logging.getLogger("whatsapp_client")

GRAPH_API_BASE = "https://graph.facebook.com"


class WhatsAppConfigError(RuntimeError):
    pass


class WhatsAppClient:
    def __init__(
        self,
        access_token: str | None = None,
        phone_number_id: str | None = None,
        api_version: str | None = None,
    ) -> None:
        self.access_token = access_token or os.environ.get("WHATSAPP_ACCESS_TOKEN")
        self.phone_number_id = phone_number_id or os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
        self.api_version = api_version or os.environ.get("WHATSAPP_API_VERSION", "v20.0")

        if not self.access_token or not self.phone_number_id:
            raise WhatsAppConfigError(
                "WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID must be set. "
                "Falling back to mock mode is the caller's responsibility."
            )

    @property
    def _base_url(self) -> str:
        return f"{GRAPH_API_BASE}/{self.api_version}/{self.phone_number_id}/messages"

    async def send_text_message(self, to_whatsapp_number: str, body: str) -> dict[str, Any]:
        """Send a free-form text message. Only valid within Meta's 24-hour
        customer service window (i.e. the user messaged you recently);
        outside that window, a pre-approved message template is required."""
        payload = {
            "messaging_product": "whatsapp",
            "to": to_whatsapp_number,
            "type": "text",
            "text": {"body": body},
        }
        headers = {"Authorization": f"Bearer {self.access_token}"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(self._base_url, json=payload, headers=headers)

        if response.status_code >= 400:
            # Never log the message body or full phone number.
            logger.error(
                "WhatsApp send failed: status=%s number_suffix=%s",
                response.status_code,
                to_whatsapp_number[-4:] if to_whatsapp_number else "????",
            )
            response.raise_for_status()

        return response.json()


class MockWhatsAppClient:
    """Drop-in replacement for local/demo use with no real credentials.
    Records sent messages in memory instead of calling the Graph API."""

    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []

    async def send_text_message(self, to_whatsapp_number: str, body: str) -> dict[str, Any]:
        record = {"to": to_whatsapp_number, "body": body, "mock": True}
        self.sent_messages.append(record)

        print(f"[MOCK WHATSAPP SEND] To: {to_whatsapp_number}")
        print(f"[MOCK WHATSAPP SEND] Message: {body}")

        return record


def get_whatsapp_client() -> WhatsAppClient | MockWhatsAppClient:
    """Factory: returns a real client if credentials are configured, else the
    mock client. This lets the rest of the app stay agnostic to which one
    it's talking to."""
    try:
        return WhatsAppClient()
    except WhatsAppConfigError:
        logger.warning("WhatsApp credentials not configured; using MockWhatsAppClient.")
        return MockWhatsAppClient()
