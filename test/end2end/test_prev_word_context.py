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
orchestrator's private ``SessionManager.sessions`` registry (a named,
non-default session is never even registered there). It captures the
session carried on the universal §9.5 ``ovos.utterance.handled`` end-marker
via ``ovoscope``'s ``CaptureSession`` (which deserializes its own
independent copy of every message off the bus, so it never shares object
identity with whatever the orchestrator is still holding) and re-declares
that captured session on the next turn's utterance, exactly as a real
client would.

``ovos.utterance.handled`` is the correct observation point, not the §8
``ovos.intent.handler.complete`` terminal: the handler-lifecycle terminal is
always ``Message.forward``-derived, and ``forward`` unconditionally
re-stamps its derived message with whatever the *live* session currently
holds (OVOS-MSG-1 §5.1's own bookkeeping) - so it reflects the write
regardless of whether OVOS-SESSION-2 §2.6's completion sync ran. The §9.5
end-marker is emitted from the plain dispatch snapshot instead, so it only
carries the "prev_word" write once §2.6 has folded it in - the deciding
observation point that actually depends on ovos-core>=3.2.5a1.
"""
import uuid
from unittest import TestCase

from ovos_bus_client.message import Message
from ovoscope import CaptureSession, get_minicroft

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

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def _say(self, utterance, session=None):
        """Emit ``utterance``, optionally re-declaring a ``session`` dict
        captured from a previous turn's ``ovos.utterance.handled`` end-
        marker (a fresh client-chosen session id is used when ``session`` is
        omitted, never one pulled from the orchestrator's registry).

        Returns ``(spoken_utterances, carried_session)`` where
        ``carried_session`` is the session dict pulled off this turn's
        ``ovos.utterance.handled`` message context (the wire carrier of
        whatever ``intent_context`` the handler just wrote, once
        OVOS-SESSION-2 §2.6 has synced it into the round's working session).
        """
        session = session or {"session_id": f"prev-word-{uuid.uuid4()}"}
        msg = Message("recognizer_loop:utterance",
                      {"utterances": [utterance], "lang": LANG},
                      {"session": session})
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
