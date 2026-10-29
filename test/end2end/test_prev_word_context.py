"""End-to-end coverage for the "prev_word" follow-up context.

A successful lookup through ``search_wordnet.intent`` writes the word to the
OVOS-CONTEXT-1 shared-scope "prev_word" context. A follow-up in the same
conversation then refers back to it: "what does wordnet say about it" looks
the remembered word up instead of re-prompting.

The test reads the session that the ``ovos.utterance.handled`` end-marker
carries, and declares that session on the next utterance, as a client does.
It never reads the private ``SessionManager.sessions`` registry.
"""
import uuid
from unittest import TestCase

from ovos_bus_client.message import Message
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-wordnet.openvoiceos"
LANG = "en-US"


class TestPrevWordContext(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID], lang=LANG)
        cls.skill = cls.minicroft.plugin_skills[SKILL_ID].instance
        cls.skill.engine.query = lambda *a, **k: [("a stubbed definition", 0.9)]
        cls.skill.engine.get_definition = lambda *a, **k: "a stubbed definition"

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def _say(self, utterance, session=None):
        """Emit ``utterance`` and return what was spoken and the session that
        ``ovos.utterance.handled`` carried."""
        session = session or {"session_id": f"prev-word-{uuid.uuid4()}", "lang": LANG}
        msg = Message("recognizer_loop:utterance",
                      {"utterances": [utterance], "lang": LANG},
                      {"session": session, "lang": LANG})
        capture = CaptureSession(self.minicroft, eof_msgs=["ovos.utterance.handled"])
        capture.capture(msg, timeout=20)
        responses = capture.finish()
        spoken = [m.data.get("utterance", "") for m in responses
                  if m.msg_type == "ovos.utterance.speak"]
        carried = {}
        for m in responses:
            if m.msg_type == "ovos.utterance.handled" and m.context.get("session"):
                carried.update(m.context["session"])
        return spoken, carried

    def test_followup_resolves_from_prev_word_context(self):
        _, session = self._say("search wordnet for serendipity")
        self.assertEqual(session["intent_context"]["prev_word"]["value"], "serendipity")
        spoken, _ = self._say("what does wordnet say about it", session=session)
        self.assertEqual(spoken, ["a stubbed definition"])

    def test_no_prior_word_still_reprompts(self):
        spoken, _ = self._say("what does wordnet say about it")
        self.assertEqual(spoken, ["I did not catch which word you mean"])

