"""
Unit tests for ovos-skill-wordnet.

All tests are offline — WordnetRetrievalEngine is mocked so no WordNet
data or translation plugin is required.
"""
import os
import unittest
from unittest.mock import MagicMock, patch, call

from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

LOCALE_EN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "ovos_skill_wordnet", "locale", "en-US",
)


def _lines(name):
    """Non-comment, non-blank lines of an en-US locale resource."""
    with open(os.path.join(LOCALE_EN, name)) as f:
        return [ln.strip() for ln in f
                if ln.strip() and not ln.lstrip().startswith("#")]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill():
    """Instantiate WordnetSkill with a mocked engine and a FakeBus."""
    with patch("ovos_skill_wordnet.WordnetRetrievalEngine") as mock_cls:
        mock_engine = MagicMock()
        mock_cls.return_value = mock_engine
        from ovos_skill_wordnet import WordnetSkill
        skill = WordnetSkill(bus=FakeBus(), skill_id="test.wordnet")
        skill.engine = mock_engine
        return skill, mock_engine


def _message(data=None):
    return Message("ovos.skills.test", data=data or {})


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestSkillInit(unittest.TestCase):

    def test_engine_created_on_initialize(self):
        skill, engine = _make_skill()
        self.assertIsNotNone(skill.engine)

    def test_runtime_requirements_offline(self):
        skill, _ = _make_skill()
        req = skill.runtime_requirements
        self.assertFalse(req.requires_internet)
        self.assertFalse(req.requires_network)
        self.assertTrue(req.no_internet_fallback)
        self.assertTrue(req.no_network_fallback)


# ---------------------------------------------------------------------------
# Explicit intent — handle_search
# ---------------------------------------------------------------------------

class TestHandleSearch(unittest.TestCase):

    def setUp(self):
        self.skill, self.engine = _make_skill()
        self.skill.speak = MagicMock()
        self.skill.speak_dialog = MagicMock()

    def test_speaks_first_result(self):
        self.engine.query.return_value = [("a loyal companion", 0.9)]
        self.skill.handle_search(_message({"word": "dog"}))
        self.skill.speak.assert_called_once_with("a loyal companion")
        self.skill.speak_dialog.assert_not_called()

    def test_speaks_no_answer_when_empty(self):
        self.engine.query.return_value = []
        self.skill.handle_search(_message({"word": "xyzzy"}))
        self.skill.speak_dialog.assert_called_once_with("no_answer")
        self.skill.speak.assert_not_called()

    def test_engine_called_with_skill_lang(self):
        with patch.object(type(self.skill), "lang", new_callable=lambda: property(lambda s: "es-ES")):
            self.engine.query.return_value = [("respuesta", 0.9)]
            self.skill.handle_search(_message({"word": "perro"}))
            self.engine.query.assert_called_once()
            _, kwargs = self.engine.query.call_args
            self.assertEqual(kwargs.get("lang"), "es-ES")

    def test_engine_called_with_k_1(self):
        self.engine.query.return_value = [("answer", 0.9)]
        self.skill.handle_search(_message({"word": "dog"}))
        _, kwargs = self.engine.query.call_args
        self.assertEqual(kwargs.get("k"), 1)


# ---------------------------------------------------------------------------
# Common Query
# ---------------------------------------------------------------------------

class TestMatchCommonQuery(unittest.TestCase):

    def setUp(self):
        self.skill, self.engine = _make_skill()

    def test_returns_definition_with_confidence(self):
        self.engine.get_definition.return_value = "a domestic canine"
        answer, conf = self.skill.match_common_query("dog", "en-US")
        self.assertEqual(answer, "a domestic canine")
        self.assertAlmostEqual(conf, 0.6)

    def test_returns_none_when_no_definition(self):
        self.engine.get_definition.return_value = None
        answer, conf = self.skill.match_common_query("xyzzy", "en-US")
        self.assertIsNone(answer)
        self.assertAlmostEqual(conf, 0.0)

    def test_passes_short_lang_to_engine(self):
        self.engine.get_definition.return_value = "un chien"
        self.skill.match_common_query("chien", "fr-FR")
        self.engine.get_definition.assert_called_once_with("chien", lang="fr")

    def test_strips_region_from_lang(self):
        self.engine.get_definition.return_value = "ein Hund"
        self.skill.match_common_query("Hund", "de-DE")
        _, kwargs = self.engine.get_definition.call_args
        self.assertEqual(kwargs["lang"], "de")


# ---------------------------------------------------------------------------
# Fallback handler
# ---------------------------------------------------------------------------

class TestFallback(unittest.TestCase):

    def setUp(self):
        self.skill, self.engine = _make_skill()
        self.skill.speak = MagicMock()
        self.skill.voc_match = MagicMock()

    def _fallback_msg(self, utterance, lang="en-US"):
        with patch("ovos_skill_wordnet.SessionManager") as mock_sm:
            mock_sm.get.return_value.lang = lang
            return self.skill.handle_fallback(
                _message({"utterance": utterance})
            )

    def test_returns_false_when_no_keyword_match(self):
        self.skill.voc_match.return_value = False
        result = self._fallback_msg("play some jazz")
        self.assertFalse(result)
        self.engine.query.assert_not_called()

    def test_returns_true_and_speaks_on_match(self):
        self.skill.voc_match.return_value = True
        self.engine.query.return_value = [("a canine mammal", 0.9)]
        result = self._fallback_msg("what is the definition of dog")
        self.assertTrue(result)
        self.skill.speak.assert_called_once_with("a canine mammal")

    def test_returns_false_when_engine_has_no_answer(self):
        self.skill.voc_match.return_value = True
        self.engine.query.return_value = []
        result = self._fallback_msg("what is the definition of xyzzy")
        self.assertFalse(result)
        self.skill.speak.assert_not_called()

    def test_voc_match_called_with_wordnet_query(self):
        self.skill.voc_match.return_value = False
        self._fallback_msg("what is the meaning of happy", lang="en-US")
        self.skill.voc_match.assert_called_once()
        args = self.skill.voc_match.call_args[0]
        self.assertIn("WordnetQuery", args)

    def test_engine_called_with_full_utterance(self):
        self.skill.voc_match.return_value = True
        self.engine.query.return_value = [("answer", 0.9)]
        self._fallback_msg("what is the antonym of happy", lang="fr-FR")
        call_args = self.engine.query.call_args
        self.assertEqual(call_args[0][0], "what is the antonym of happy")

    def test_engine_called_with_session_lang(self):
        self.skill.voc_match.return_value = True
        self.engine.query.return_value = [("réponse", 0.9)]
        self._fallback_msg("quelle est la définition de chien", lang="fr-FR")
        _, kwargs = self.engine.query.call_args
        self.assertEqual(kwargs.get("lang"), "fr-FR")

    def test_exception_in_engine_returns_false(self):
        self.skill.voc_match.return_value = True
        self.engine.query.side_effect = Exception("network error")
        result = self._fallback_msg("what is the definition of dog")
        self.assertFalse(result)

    def test_returns_false_on_empty_utterance(self):
        self.skill.voc_match.return_value = False
        result = self._fallback_msg("")
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# en-US locale resources
# ---------------------------------------------------------------------------

class TestEnglishLocale(unittest.TestCase):

    def test_every_intent_line_has_word_slot(self):
        lines = _lines("search_wordnet.intent")
        self.assertTrue(lines)
        for ln in lines:
            self.assertIn("{word}", ln, f"missing open slot: {ln!r}")

    def test_intent_declares_only_the_word_slot(self):
        import re
        for ln in _lines("search_wordnet.intent"):
            for slot in re.findall(r"{(\w+)}", ln):
                self.assertEqual(slot, "word", f"undefined slot in: {ln!r}")

    def test_intent_covers_dictionary_and_thesaurus_phrasings(self):
        blob = " ".join(_lines("search_wordnet.intent"))
        for kw in ("define", "definition", "meaning", "mean",
                   "synonym", "antonym", "opposite"):
            self.assertIn(kw, blob, f"no coverage for {kw!r}")

    def test_word_blacklist_references_pronoun_and_determiner_voc(self):
        # OVOS-INTENT-2 §4.3 slot-value exclusion: the blacklist delegates to
        # the pronoun/determiner vocabularies so anaphora ("what does it mean")
        # stay unresolved.
        lines = _lines("word.blacklist")
        self.assertIn("<pronoun>", lines)
        self.assertIn("<determiner>", lines)

    def test_pronoun_and_determiner_voc_cover_anaphora(self):
        pron = " ".join(_lines("pronoun.voc"))
        for p in ("it", "he", "she", "they"):
            self.assertIn(p, pron, f"pronoun {p!r} not covered")
        det = " ".join(_lines("determiner.voc"))
        for d in ("this", "that", "these", "those"):
            self.assertIn(d, det, f"determiner {d!r} not covered")


class TestCanAnswer(unittest.TestCase):
    """The skills service pings every fallback skill and routes only to the
    ones that pong. FallbackSkill.can_answer raises NotImplementedError, so a
    skill that does not override it drops out of the fallback pipeline with no
    error the user ever sees."""

    def setUp(self):
        self.skill, self.engine = _make_skill()

    def _ping(self, utterance):
        return Message("ovos.skills.fallback.ping",
                       data={"utterances": [utterance]})

    def test_claims_a_definition_question(self):
        self.assertTrue(self.skill.can_answer(self._ping("what is the meaning of stoic")))

    def test_declines_an_unrelated_question(self):
        self.assertFalse(self.skill.can_answer(self._ping("turn on the kitchen light")))

    def test_ping_does_not_query_the_engine(self):
        # the ping fires for every fallback utterance; a lookup here would run
        # on questions this skill never handles
        self.skill.can_answer(self._ping("define stoic"))
        self.engine.query.assert_not_called()

    def test_ping_emits_a_pong(self):
        replies = []
        self.skill.bus.on("ovos.skills.fallback.pong", lambda m: replies.append(m))
        self.skill.bus.emit(self._ping("define stoic"))
        self.assertEqual(len(replies), 1)
        self.assertTrue(replies[0].data["can_handle"])
        self.assertEqual(replies[0].data["skill_id"], "test.wordnet")


if __name__ == "__main__":
    unittest.main()
