"""
Wraps the Anthropic API for the one part of the conversation that should be
AI-generated: open-ended worker questions (FREEFORM_QA state).

Everything else in the conversation (consent, questionnaire, linking) is
handled by the deterministic state machine in conversation_service.py on
purpose — a safety-relevant, consent-driven flow should not depend on a
model's free-form judgment for wording that has legal/compliance weight.
"""
from __future__ import annotations

import os

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None  # allows the module to import even before the dep is installed

SYSTEM_PROMPT = """\
You are the StationShield assistant, answering a subway worker's question over WhatsApp
about environmental conditions and workplace safety at their assigned station.

Ground rules:
- You are not a medical professional. Never diagnose, never say a worker is "fit" or
  "unfit" to work, never recommend a specific medical treatment.
- You may explain what the environmental indicators shown in the app mean in plain
  language, and point the worker toward official safety procedures or a human reviewer.
- If a question is about symptoms, health conditions, or anything requiring medical
  judgment, tell the worker to contact their supervisor or occupational health team,
  and offer to log a concern for human review instead of answering it yourself.
- Keep replies short (2-4 sentences) — this is a WhatsApp chat, not an essay.
- Never claim environmental data is "live" or "verified" unless the app data explicitly
  says so; treat all figures you're given as provided, not something you can look up.
"""


def get_ai_reply(user_message: str, station_context: dict | None = None) -> str:
    if anthropic is None:
        return (
            "I can't reach the AI assistant right now. Please contact your supervisor "
            "or use the 'Raise a concern' option for anything urgent."
        )

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    context_str = ""
    if station_context:
        context_str = (
            f"\n\nStation context available to you (demo/synthetic data unless noted):\n"
            f"{station_context}"
        )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=SYSTEM_PROMPT + context_str,
        messages=[{"role": "user", "content": user_message}],
    )

    return "".join(block.text for block in response.content if block.type == "text").strip()
