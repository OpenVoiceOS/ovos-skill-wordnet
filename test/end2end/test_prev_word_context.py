"""End-to-end coverage for the "prev_word" follow-up context.

A successful lookup through ``search_wordnet.intent`` remembers the word it
just looked up (OVOS-CONTEXT-1 shared-scope "prev_word"), so a follow-up in
the SAME conversation can refer back to it instead of repeating it: "what
does that mean" resolves the unresolved {word} slot from context instead of
re-prompting, and "spell that" spells the remembered word out. Without the
context write this suite's positive cases fail: the follow-up utterance re-
prompts ("I did not catch which word you mean") exactly like the negative
case below, because handle_search never saw a real word to remember.
"""
import time
from unittest import TestCase

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session, SessionManager
from ovoscope import get_minicroft

SKILL_ID = "ovos-skill-wordnet.openvoiceos"
LANG = "en-US"
PIPELINE = [
    "ovos-padatious-pipeline-plugin-high",
    "ovos-padatious-pipeline-plugin-medium",
]


class TestPrevWordContext(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID])
        cls.skill = cls.minicroft.plugin_skills[SKILL_ID].instance
        cls.skill.engine.query = lambda *a, **k: [("a stubbed definition", 0.9)]
        cls.skill.engine.get_definition = lambda *a, **k: "a stubbed definition"
        cls.bus = cls.minicroft.bus

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def _say(self, utterance, session_id):
        """Emit ``utterance`` in the multi-turn conversation ``session_id``.

        The in-process ``SessionManager`` registry (populated by the
        PREVIOUS turn's dispatch, same process as this test) is the source
        of the live ``intent_context`` for this session; a brand-new client
        ``Session`` object here would otherwise carry no context at all and
        every turn would look like the first one.
        """
        spoken = []
        stop = self.bus.on("speak", lambda m: spoken.append(m.data.get("utterance", "")))
        session = SessionManager.sessions.get(session_id) or Session(session_id)
        session.lang = LANG
        session.pipeline = list(PIPELINE)
        self.bus.emit(Message("recognizer_loop:utterance",
                              {"utterances": [utterance], "lang": LANG},
                              {"session": session.serialize()}))
        time.sleep(3)
        self.bus.remove("speak", stop) if callable(stop) else None
        return spoken

    def test_followup_resolves_from_prev_word_context(self):
        session_id = "prev-word-followup"
        self._say("define serendipity", session_id)
        spoken = self._say("what does that mean", session_id)
        self.assertIn("a stubbed definition", spoken,
                      f"follow-up did not resolve from prev_word context: {spoken}")

    def test_spell_followup_spells_prev_word(self):
        session_id = "prev-word-spell"
        self._say("define ephemeral", session_id)
        spoken = self._say("spell that", session_id)
        self.assertTrue(
            any("ephemeral" in u.lower() and "e" in u.lower() for u in spoken),
            f"expected the remembered word spelled out, got: {spoken}",
        )

    def test_no_prior_word_still_reprompts(self):
        session_id = "prev-word-none"
        spoken = self._say("what does that mean", session_id)
        self.assertTrue(
            any("which word" in u.lower() for u in spoken),
            f"expected an unresolved-word re-prompt with no prior context, got: {spoken}",
        )
