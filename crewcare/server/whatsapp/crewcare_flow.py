"""
Drives the CrewCare conversation over WhatsApp.

The wording, the questions, the branching and the skip behaviour all come
from `script.json`, which is generated from `src/conversation/script.ts` —
the same file the web simulator runs on. One source of truth, so the thread a
worker sees on their phone cannot drift from the one demoed in the browser.

What this module adds on top of the script is the part that is specific to a
text channel: people type words, not tap chips. `match_option` accepts the
full label, a unique prefix, or the option's position ("1", "2", ...), which
is how someone actually replies to a list in a text message.

Three step kinds cannot work natively over WhatsApp and are handled here
rather than pretended away:

  attach   media arrives as a webhook event, not as text — see webhook.py
  connect  HealthKit and CommonHealth need a native app; WhatsApp cannot
           reach either, so the step offers a hand-off link and accepts a
           decline
  report   free text, which WhatsApp does natively
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).with_name("script.json")

# Words a worker might reasonably send to decline a skippable step.
_SKIP_WORDS = {"skip", "no thanks", "not now", "nothing", "pass", "none", "nothing to report"}
_STOP_WORDS = {"stop", "quit", "cancel", "exit", "unsubscribe"}

# Phone keyboards do not produce en dashes. An option labelled "1–4 weeks"
# will be typed "1-4 weeks", and matching that literally would reject a
# perfectly clear answer, so comparison happens on a normalised form.
_DASHES = str.maketrans({"\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2019": "'", "\u2018": "'"})


def _normalise(text: str) -> str:
    """Lowercase, unify dashes and quotes, and collapse whitespace."""
    return " ".join(text.translate(_DASHES).lower().split())


def load_script(path: Path = SCRIPT_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


@dataclass(frozen=True)
class Reply:
    """What to send back, and where the conversation now sits."""

    messages: list[str]
    step_id: str | None
    finished: bool = False


class CrewCareFlow:
    def __init__(self, script: dict[str, Any] | None = None) -> None:
        self.script = script or load_script()
        self.steps: dict[str, dict[str, Any]] = {s["id"]: s for s in self.script["steps"]}
        self.first_step: str = self.script["firstStep"]

    # ── script walking ────────────────────────────────────────────────────

    def _render_line(self, line: dict[str, Any], answers: dict[str, str]) -> str | None:
        if "special" in line:
            return self._summary(answers) if line["special"] == "summary" else None
        text = line["text"]
        # The web app paints the bracketed phrase in Signal Orange; a text
        # channel has no colour, so the brackets simply come off.
        text = text.replace("[", "").replace("]", "")
        if line.get("sample"):
            text = f"[sample]\n{text}"
        return text

    def _collect(self, step_id: str, answers: dict[str, str]) -> tuple[str, list[str]]:
        """Gather everything the bot says before it next needs input.

        Mirrors `collect()` in machine.ts: `say` steps fall through.
        """
        messages: list[str] = []
        current = step_id
        for _ in range(len(self.steps) + 1):
            step = self.steps.get(current)
            if step is None:
                break
            for line in step["lines"]:
                rendered = self._render_line(line, answers)
                if rendered:
                    messages.append(rendered)
            prompt = self._prompt_for(step)
            if step["kind"] == "say" and step.get("next"):
                current = step["next"]
                continue
            if prompt:
                messages.append(prompt)
            return current, messages
        return current, messages

    def _prompt_for(self, step: dict[str, Any]) -> str | None:
        """The 'how to reply' line a text channel needs and a UI does not."""
        kind = step["kind"]
        options = step.get("options") or []

        if kind in ("choice", "connect") and options:
            listed = "\n".join(f"{i + 1}. {o['label']}" for i, o in enumerate(options))
            tail = f"\n\nOr reply {step.get('skipLabel', 'SKIP').upper()}." if step.get("allowSkip") else ""
            if kind == "connect":
                tail = (
                    "\n\nConnecting a health app needs the CrewCare app on your phone — "
                    "reply with a number and I'll text you the link."
                ) + tail
            return f"{listed}{tail}"

        if kind == "attach":
            return "Send a photo or PDF, or reply SKIP."
        if kind == "report":
            return "Reply with what's wrong, or reply SKIP."
        if kind == "text":
            return None  # The question itself is the prompt.
        return None

    # ── answering ─────────────────────────────────────────────────────────

    def match_option(self, step: dict[str, Any], text: str) -> str | None:
        """Resolve typed text to an option id: label, unique prefix, or index."""
        options = step.get("options") or []
        cleaned = _normalise(text)
        if not cleaned:
            return None

        for option in options:
            if cleaned in (_normalise(option["label"]), _normalise(option["id"])):
                return option["id"]

        if cleaned.isdigit():
            index = int(cleaned) - 1
            if 0 <= index < len(options):
                return options[index]["id"]

        partial = [o for o in options if _normalise(o["label"]).startswith(cleaned)]
        return partial[0]["id"] if len(partial) == 1 else None

    def is_skip(self, step: dict[str, Any], text: str) -> bool:
        if not step.get("allowSkip"):
            return False
        cleaned = _normalise(text)
        label = _normalise(step.get("skipLabel") or "")
        return cleaned in _SKIP_WORDS or (bool(label) and cleaned == label)

    def _next_after(self, step: dict[str, Any], option_id: str | None, skipped: bool) -> str | None:
        if skipped:
            return step.get("skipTo") or step.get("next")
        if option_id and step.get("branch", {}).get(option_id):
            return step["branch"][option_id]
        return step.get("next")

    def start(self) -> Reply:
        step_id, messages = self._collect(self.first_step, {})
        return Reply(messages=messages, step_id=step_id)

    def advance(self, step_id: str | None, text: str, answers: dict[str, str]) -> Reply:
        """Apply one inbound message. `answers` is mutated with what was said."""
        if _normalise(text) in _STOP_WORDS:
            return Reply(
                messages=["Okay — no more messages. Reply START any time to pick up again."],
                step_id=None,
                finished=True,
            )

        if step_id is None or step_id not in self.steps:
            return self.start()

        step = self.steps[step_id]
        kind = step["kind"]
        skipped = self.is_skip(step, text)
        option_id: str | None = None

        if not skipped:
            if kind in ("choice", "connect"):
                option_id = self.match_option(step, text)
                if option_id is None:
                    # Never guess at an answer; ask again with the options.
                    return Reply(
                        messages=["Sorry, I didn't catch that.", self._prompt_for(step) or ""],
                        step_id=step_id,
                    )
                answers[step_id] = next(
                    o["label"] for o in step["options"] if o["id"] == option_id
                )
            elif kind in ("text", "report", "attach"):
                if not text.strip():
                    return Reply(messages=[self._prompt_for(step) or ""], step_id=step_id)
                answers[step_id] = text.strip()
            else:
                answers[step_id] = text.strip()
        else:
            answers[step_id] = "Skipped"

        ack = step.get("skipAck") if skipped else step.get("ack")
        target = self._next_after(step, option_id, skipped)

        messages = [ack] if ack else []
        if target is None:
            return Reply(messages=messages, step_id=None, finished=True)

        next_id, more = self._collect(target, answers)
        messages.extend(more)
        finished = self.steps.get(next_id, {}).get("kind") == "done"
        return Reply(messages=messages, step_id=next_id, finished=finished)

    # ── closing summary ───────────────────────────────────────────────────

    def _summary(self, answers: dict[str, str]) -> str:
        rows = [
            f"{step['summaryLabel']}: {answers[step['id']]}"
            for step in self.script["steps"]
            if step.get("summaryLabel") and step["id"] in answers
        ]
        if not rows:
            return "Nothing recorded."
        return "What you shared:\n" + "\n".join(f"- {row}" for row in rows)
