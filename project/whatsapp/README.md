# WhatsApp Cloud API integration — StationShield

Implements the webhook + linking + conversation pieces from the project spec
(section 8–9). Designed to drop into an existing FastAPI backend.

## Files

| File | Purpose |
|---|---|
| `models.py` | SQLAlchemy models: `LinkingCode`, `WhatsAppLink`, `ConversationSession`, `ProcessedWebhookEvent` |
| `whatsapp_client.py` | Sends messages via the Graph API; `MockWhatsAppClient` fallback with no credentials |
| `linking_service.py` | One-time code generation/verification, rate limiting, unlink |
| `conversation_service.py` | The state machine (START → CONSENT → ... → COMPLETED) |
| `ai_client.py` | Anthropic API call for the one open-ended (`FREEFORM_QA`) branch |
| `webhook.py` | FastAPI router: `GET`/`POST /api/webhooks/whatsapp`, linking endpoints |
| `db.py`, `auth.py` | **Placeholders** — replace with your real DB session and auth dependencies |

## Wiring into your app

```python
# main.py
from whatsapp_integration.webhook import router as whatsapp_router
app.include_router(whatsapp_router)
```

Delete `db.py`/`auth.py` and point `webhook.py`'s imports at your real
`get_db` and `get_current_employee_id` dependencies — these two files exist
only so the module can run standalone.

## Local testing without real WhatsApp credentials

`get_whatsapp_client()` automatically falls back to `MockWhatsAppClient` if
`WHATSAPP_ACCESS_TOKEN` / `WHATSAPP_PHONE_NUMBER_ID` aren't set, so you can
exercise the whole flow — linking, consent, questionnaire, AI Q&A — by
calling `conversation_service.handle_incoming_message()` directly or by
POSTing a synthetic webhook payload:

```bash
curl -X POST http://localhost:8000/api/webhooks/whatsapp \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{"changes": [{"value": {"messages": [
      {"id": "wamid.test1", "from": "15551234567", "text": {"body": "123456"}}
    ]}}]}]
  }'
```

This is exactly what your web-app WhatsApp *simulator* (spec section 18)
should call under the hood, so both the mock UI and the real integration
exercise identical backend logic.

## Testing with the real Cloud API

1. `pip install -r requirements.txt`, copy `.env.example` to `.env` and fill
   in values from your Meta Developer app.
2. `ngrok http 8000`, set the ngrok HTTPS URL + `/api/webhooks/whatsapp` as
   the callback URL in Meta's dashboard, using the same `WHATSAPP_VERIFY_TOKEN`.
3. From your logged-in web app, call `POST /api/whatsapp/linking/start` to
   get a code, text that code to your WhatsApp test number, confirm you get
   the "now linked" reply.
4. Send `START` and walk through the flow.

## What's intentionally NOT done here

- No message *templates* (needed only for messages sent outside a 24-hour
  reply window, e.g. proactive alerts) — out of scope for a hackathon demo.
- No async task queue — the webhook handler processes inline, per the spec's
  guidance to keep it simple for the MVP. Note the comment in `webhook.py` if
  you add real ML inference or file processing, which should be queued.
- No file/media handling for report uploads — `REPORT_UPLOAD` state has a
  stub comment showing where secure storage + review would hook in.
- Signature verification (`WHATSAPP_APP_SECRET`) is skipped with a warning if
  unset, so the demo runs without it — don't skip it in anything beyond a
  local demo.
