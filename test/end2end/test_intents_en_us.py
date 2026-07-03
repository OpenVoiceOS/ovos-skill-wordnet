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
INTENT_EVENT = f"{SKILL_ID}:search_wordnet.intent"
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
        self.bus.on(INTENT_EVENT,
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
    def test_what_does_word_mean(self):
        words, _ = self._run("what does serendipity mean")
        self.assertIn("serendipity", words)

    def test_define_word(self):
        words, _ = self._run("define ephemeral")
        self.assertIn("ephemeral", words)

    def test_synonym_of_word(self):
        words, _ = self._run("synonym of happy")
        self.assertIn("happy", words)


class TestPronounSlotExclusion(_RoutingTest):
    def test_pronoun_does_not_fill_word_slot(self):
        """``word.blacklist`` refuses an anaphoric pronoun in the {word} slot.

        "what does it mean" binds {word}="it"; the slot-value exclusion
        (OVOS-INTENT-2 §4.3) rejects that anaphoric filler, so the skill never
        looks it up and instead re-prompts for the referent.
        """
        words, spoken = self._run("what does it mean")
        # the pronoun is never looked up: the stubbed definition never speaks
        self.assertNotIn("a stubbed definition", spoken,
                         f"pronoun was looked up as a word: {spoken}")
        # the unresolved slot triggers a clarification prompt instead
        self.assertTrue(
            any("which word" in u.lower() for u in spoken),
            f"expected an unresolved-word re-prompt, got: {spoken}",
        )
