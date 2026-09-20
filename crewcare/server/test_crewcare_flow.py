"""
Exercises the WhatsApp flow against the exported CrewCare script.

Run: python3 -m unittest discover -s server -v
No network, no database, no FastAPI — the flow is pure.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from whatsapp.crewcare_flow import CrewCareFlow


class FlowHarness:
    """Walks the flow the way a person texting would."""

    def __init__(self):
        self.flow = CrewCareFlow()
        self.answers: dict[str, str] = {}
        reply = self.flow.start()
        self.step = reply.step_id
        self.sent = list(reply.messages)
        self.finished = False

    def say(self, text: str):
        reply = self.flow.advance(self.step, text, self.answers)
        self.step = reply.step_id
        self.sent.extend(reply.messages)
        self.finished = reply.finished
        return reply

    @property
    def transcript(self) -> str:
        return "\n".join(self.sent)


class TestCrewCareFlow(unittest.TestCase):
    def test_intro_carries_the_exact_disclosure(self):
        h = FlowHarness()
        self.assertIn(
            "CrewCare is not a medical service and does not give medical advice",
            h.transcript,
        )
        self.assertEqual(h.step, "intro")

    def test_a_typed_hyphen_matches_an_en_dash_label(self):
        # Phone keyboards do not produce "1–4 weeks"; rejecting "1-4 weeks"
        # would be rejecting a clear answer.
        h = FlowHarness()
        h.say("Get started")
        h.say("Good")
        h.say("Yes")
        h.say("cough")
        h.say("1-4 weeks")
        self.assertEqual(h.step, "q5")
        self.assertEqual(h.answers["q4"], "1–4 weeks")

    def test_replies_may_be_a_number_a_label_or_a_prefix(self):
        for answer in ("1", "Get started", "get star"):
            h = FlowHarness()
            h.say(answer)
            self.assertEqual(h.step, "q1", f"{answer!r} should select the first option")

    def test_unrecognised_input_reasks_instead_of_guessing(self):
        h = FlowHarness()
        h.say("what?")
        self.assertEqual(h.step, "intro", "stays put")
        self.assertIn("didn't catch that", h.transcript)
        self.assertNotIn("q1", h.answers)

    def test_q2_yes_walks_the_symptom_questions(self):
        h = FlowHarness()
        h.say("Get started")
        h.say("Good")
        self.assertEqual(h.step, "q2")
        h.say("Yes")
        self.assertEqual(h.step, "q3")
        h.say("Dry cough after midnight tours")
        self.assertEqual(h.step, "q4")
        h.say("1-4 weeks")
        self.assertEqual(h.step, "q5")
        h.say("Happens mainly during work")
        self.assertEqual(h.step, "medical")

    def test_q2_no_skips_the_symptom_questions(self):
        h = FlowHarness()
        h.say("Get started")
        h.say("Good")
        h.say("No")
        self.assertEqual(h.step, "medical")
        self.assertNotIn("q3", h.answers)

    def test_every_health_question_can_be_skipped(self):
        h = FlowHarness()
        h.say("Get started")
        h.say("skip")
        self.assertEqual(h.step, "q2")
        h.say("skip")
        self.assertEqual(h.step, "medical", "declining Q2 declines elaborating")

    def test_skipping_never_claims_the_action_happened(self):
        h = FlowHarness()
        h.say("Get started")
        h.say("No")  # q1
        h.say("No")  # q2 -> medical
        before = len(h.sent)
        h.say("skip")  # medical
        self.assertNotIn("stays on your phone", "\n".join(h.sent[before:]))
        before = len(h.sent)
        h.say("skip")  # health app
        self.assertNotIn("Connected", "\n".join(h.sent[before:]))

    def test_declining_alerts_does_not_enrol(self):
        h = FlowHarness()
        h.say("Get started")
        h.say("Good")
        h.say("No")
        h.say("skip")   # medical
        h.say("skip")   # health app
        self.assertEqual(h.step, "notify")
        before = len(h.sent)
        h.say("No thanks")
        after = "\n".join(h.sent[before:])
        self.assertNotIn("Reply STOP", after)
        self.assertNotIn("all set", after)
        self.assertIn("won't message you", after.replace("’", "'"))

    def test_a_full_run_ends_with_a_summary(self):
        h = FlowHarness()
        h.say("Get started")
        h.say("Very good")
        h.say("Yes")
        h.say("Shortness of breath")
        h.say("1-3 months")
        h.say("Happens mainly after work")
        h.say("skip")            # medical
        h.say("Apple Health")    # health app
        h.say("Yes, daily")
        self.assertEqual(h.step, "complaint")
        h.say("Dust on the northbound platform")
        self.assertTrue(h.finished)
        self.assertIn("What you shared:", h.transcript)
        self.assertIn("Shortness of breath", h.transcript)

    def test_stop_ends_the_conversation_anywhere(self):
        h = FlowHarness()
        h.say("Get started")
        reply = h.say("STOP")
        self.assertTrue(reply.finished)
        self.assertIsNone(reply.step_id)

    def test_the_sample_alert_is_labelled_and_carries_no_numbers(self):
        h = FlowHarness()
        h.say("Get started")
        h.say("Good")
        h.say("No")
        h.say("skip")
        h.say("skip")
        h.say("Yes, daily")
        self.assertIn("[sample]", h.transcript)
        self.assertIn("Wear an N95", h.transcript)
        self.assertNotIn("2.4×", h.transcript)
        # The colour markup is stripped for a text channel.
        self.assertIn("hotter than usual", h.transcript)
        self.assertNotIn("[hotter than usual]", h.transcript)


if __name__ == "__main__":
    unittest.main()
