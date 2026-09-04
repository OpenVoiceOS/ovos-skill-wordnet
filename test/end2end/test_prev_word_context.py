"""End-to-end coverage for the "prev_word" follow-up context.

A successful lookup through ``search_wordnet.intent`` remembers the word it
just looked up (OVOS-CONTEXT-1 shared-scope "prev_word"), so a follow-up in
the SAME conversation can refer back to it instead of repeating it: "what
does that mean" resolves the unresolved {word} slot from context instead of
re-prompting, and "spell that" spells the remembered word out. Without the
context write this suite's positive cases fail: the follow-up utterance re-
prompts ("I did not catch which word you mean") exactly like the negative
case below, because handle_search never saw a real word to remember.

Verification is client-side (§3 CLIENT-MERGE): the test never reads the
orchestrator's private ``SessionManager.sessions`` registry (that registry is
default-session-only per spec and never holds a named session's state). It
captures the session carrier off the skill's OWN done-signal
(``mycroft.skill.handler.complete``, whose context is stamped with the live
session once the handler has fully returned) and re-declares that captured
session on the next turn's utterance, exactly as a real client would.
``mycroft.skill.handler.complete`` is used over ``ovos.utterance.speak``
because this skill's handler speaks BEFORE writing the "prev_word" context
(speak-then-set order, unchanged); ``ovos.utterance.speak`` fires mid-handler
and would race the context write, while ``handler.complete`` only fires after
the handler function has fully returned.
"""
import time
import uuid
from unittest import TestCase

from ovos_bus_client.message import Message
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

    def _say(self, utterance, session=None):
        """Emit ``utterance``, optionally re-declaring a ``session`` dict
        captured from a previous turn's ``mycroft.skill.handler.complete``
        (a fresh client-chosen session id is used when ``session`` is
        omitted, never one pulled from the orchestrator's registry).

        Returns ``(spoken_utterances, carried_session)`` where
        ``carried_session`` is the session dict pulled off the skill's own
        ``mycroft.skill.handler.complete`` message context for this turn
        (the wire carrier of whatever ``intent_context`` the handler just
        wrote, captured only after the handler has fully returned).
        """
        spoken = []
        carried = {}

        def _on_speak(m):
            spoken.append(m.data.get("utterance", ""))

        def _on_complete(m):
            if m.context.get("session"):
                carried.update(m.context["session"])

        stop_speak = self.bus.on("speak", _on_speak)
        stop_complete = self.bus.on("mycroft.skill.handler.complete", _on_complete)
        session = session or {"session_id": f"prev-word-{uuid.uuid4()}"}
        self.bus.emit(Message("recognizer_loop:utterance",
                              {"utterances": [utterance], "lang": LANG},
                              {"session": session}))
        time.sleep(3)
        self.bus.remove("speak", stop_speak) if callable(stop_speak) else None
        self.bus.remove("mycroft.skill.handler.complete", stop_complete) if callable(stop_complete) else None
        return spoken, carried

    def test_followup_resolves_from_prev_word_context(self):
        _, session = self._say("define serendipity")
        spoken, _ = self._say("what does that mean", session=session)
        self.assertIn("a stubbed definition", spoken,
                      f"follow-up did not resolve from prev_word context: {spoken}")

    def test_spell_followup_spells_prev_word(self):
        _, session = self._say("define ephemeral")
        spoken, _ = self._say("spell that", session=session)
        self.assertTrue(
            any("ephemeral" in u.lower() and "e" in u.lower() for u in spoken),
            f"expected the remembered word spelled out, got: {spoken}",
        )

    def test_no_prior_word_still_reprompts(self):
        spoken, _ = self._say("what does that mean")
        self.assertTrue(
            any("which word" in u.lower() for u in spoken),
            f"expected an unresolved-word re-prompt with no prior context, got: {spoken}",
        )
