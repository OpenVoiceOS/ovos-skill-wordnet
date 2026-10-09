"""End-to-end intent-routing tests for the en-US WordNet skill.

Boots an in-process MiniCroft with the skill loaded and feeds it real
utterances through the padatious pipeline, asserting where each one routes and
how the {word} slot is filled. The WordNet backend is stubbed so the suite is
deterministic and offline — routing (and slot-value exclusion) is what we
assert, not the dictionary content.
"""
import time
from unittest import TestCase

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import get_minicroft

SKILL_ID = "ovos-skill-wordnet.openvoiceos"
LANG = "en-US"
# OVOS-MSG-1 §2.1.1 builds the dispatch topic as <skill_id>:<intent_name>.
# Which spelling reaches the wire depends on the workshop vintage in the
# container: current workshop canonicalizes (no ".intent"), older releases
# (9.3.0a2 and below) build the topic from the padatious resource FILENAME and
# the authoring extension leaks onto the wire. The e2e suite pins
# ovos-core>=2.2.4a1,<2.3.0, which resolves to a workshop that still emits the
# legacy form, so the collector listens on both spellings -- the same
# both-spellings tolerance the golden-utterance suite's _matches_intent uses.
INTENT_EVENTS = (f"{SKILL_ID}:search_wordnet",
                 f"{SKILL_ID}:search_wordnet.intent")
PIPELINE = [
    "ovos-padatious-pipeline-plugin-high",
    "ovos-padatious-pipeline-plugin-medium",
]


class _RoutingTest(TestCase):
    """Shared MiniCroft harness with a stubbed WordNet engine."""

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID])
        cls.skill = cls.minicroft.plugin_skills[SKILL_ID].instance
        # keep the suite offline and deterministic: the engine always answers,
        # so a fired intent is guaranteed to speak and we can assert on routing
        cls.skill.engine.query = lambda *a, **k: [("a stubbed definition", 0.9)]
        cls.skill.engine.get_definition = lambda *a, **k: "a stubbed definition"
        cls.bus = cls.minicroft.bus

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def _run(self, utterance):
        """Emit ``utterance`` and collect the intent + speak messages it yields."""
        intents = []
        spoken = []
        for event in INTENT_EVENTS:
            self.bus.on(event,
                        lambda m: intents.append(m.data.get("word")))
        self.bus.on("speak",
                    lambda m: spoken.append(m.data.get("utterance", "")))
        session = Session(f"e2e-{abs(hash(utterance))}")
        session.lang = LANG
        session.pipeline = PIPELINE
        self.bus.emit(Message("recognizer_loop:utterance",
                              {"utterances": [utterance], "lang": LANG},
                              {"session": session.serialize()}))
        time.sleep(3)
        return intents, spoken


class TestWordnetIntentRouting(_RoutingTest):
    # The dispatch message goes out before the handler runs, so the word in
    # it proves routing only. The stubbed engine always answers "a stubbed
    # definition": asserting it was spoken proves the handler looked the
    # word up and spoke the result.
    # "define X", "what does X mean" and "synonym of X" used to be asserted
    # here as INTENT routing. They are no longer intent lines: the intent is
    # only for sentences that name WordNet, and those phrasings are answered
    # by the fallback through wordnet_query.voc. This pipeline is padatious
    # only, so it cannot see the fallback at all; the coverage for them lives
    # in test/unittests/test_skill.py::TestCanAnswer.

    def test_ask_wordnet_about_word(self):
        words, spoken = self._run("ask wordnet about serendipity")
        self.assertIn("serendipity", words)
        self.assertIn("a stubbed definition", spoken,
                      f"handler did not speak the lookup result: {spoken}")

    def test_search_wordnet_for_word(self):
        words, spoken = self._run("search word net for ephemeral")
        self.assertIn("ephemeral", words)
        self.assertIn("a stubbed definition", spoken,
                      f"handler did not speak the lookup result: {spoken}")


class TestPronounSlotExclusion(_RoutingTest):
    def test_pronoun_does_not_fill_word_slot(self):
        """``word.blacklist`` refuses an anaphoric pronoun in the {word} slot.

        "ask wordnet about it" binds {word}="it"; the slot-value exclusion
        (OVOS-INTENT-2 §4.3) rejects that anaphoric filler, so the skill never
        looks it up and instead re-prompts for the referent.
        """
        words, spoken = self._run("ask wordnet about it")
        # the pronoun is never looked up: the stubbed definition never speaks
        self.assertNotIn("a stubbed definition", spoken,
                         f"pronoun was looked up as a word: {spoken}")
        # the unresolved slot triggers a clarification prompt instead
        self.assertTrue(
            any("which word" in u.lower() for u in spoken),
            f"expected an unresolved-word re-prompt, got: {spoken}",
        )
