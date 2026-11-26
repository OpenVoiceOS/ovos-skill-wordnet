"""End-to-end coverage for the shared "word" context.

A successful lookup through ``search_wordnet.intent`` writes the word to the
OVOS-CONTEXT-1 shared-scope "word" entry. A later turn that leaves its own
``{word}`` slot unresolved gets the remembered word from the engine
(OVOS-CONTEXT-1 §7): "what does wordnet say about it" looks it up again, and
ovos-skill-spelling spells it for "spell that".

The test reads the session that the ``ovos.utterance.handled`` end-marker
carries, and declares that session on the next utterance, as a client does.
"""
import uuid
from unittest import TestCase

from ovos_bus_client.message import Message
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-wordnet.openvoiceos"
SPELLING_ID = "skill-ovos-spelling.openvoiceos"
LANG = "en-US"


class TestWordContext(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID, SPELLING_ID], lang=LANG)
        cls.skill = cls.minicroft.plugin_skills[SKILL_ID].instance
        cls.skill.engine.query = lambda *a, **k: [("a stubbed definition", 0.9)]

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def _say(self, utterance, session=None):
        """Emit ``utterance`` and return what was spoken and the session that
        ``ovos.utterance.handled`` carried."""
        session = session or {"session_id": f"word-{uuid.uuid4()}", "lang": LANG}
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

    def test_followup_resolves_from_word_context(self):
        _, session = self._say("search wordnet for serendipity")
        self.assertEqual(session["intent_context"]["word"]["value"], "serendipity")
        spoken, _ = self._say("what does wordnet say about it", session=session)
        self.assertEqual(spoken, ["a stubbed definition"])

    def test_spelling_skill_spells_the_looked_up_word(self):
        _, session = self._say("search wordnet for ephemeral")
        spoken, _ = self._say("spell that", session=session)
        self.assertEqual(spoken, ["; ".join("ephemeral").upper()])

    def test_no_prior_word_still_reprompts(self):
        spoken, _ = self._say("what does wordnet say about it")
        self.assertEqual(spoken, ["I did not catch which word you mean"])
