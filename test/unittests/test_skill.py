"""
Unit tests for ovos-skill-wordnet.

All tests are offline — WordnetRetrievalEngine is mocked so no WordNet
data or translation plugin is required.
"""
import unittest
from unittest.mock import MagicMock, patch, call

from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus


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


if __name__ == "__main__":
    unittest.main()
