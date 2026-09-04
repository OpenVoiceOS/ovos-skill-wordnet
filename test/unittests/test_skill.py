"""
Unit tests for ovos-skill-wordnet.

All tests are offline — WordnetRetrievalEngine is mocked so no WordNet
data or translation plugin is required.
"""
import os
import unittest
from unittest.mock import MagicMock, patch, call

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session, SessionManager
from ovos_core.intent_services.dispatcher import IntentDispatcher
from ovos_core.intent_services.service import IntentService
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


def _message_with_session(data, session):
    msg = Message("ovos.skills.test", data=data or {})
    msg.context["session"] = session.serialize()
    return msg


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

    def test_engine_exception_does_not_propagate(self):
        # Regression: an uncaught exception here (e.g. the wn thread-safety
        # bug firing mid-query) used to escape handle_search entirely. The
        # framework's generic handler-error path then tried to speak this
        # skill's "skill.error" dialog, which doesn't exist for any locale,
        # so it fell back to literally saying "skill.error" out loud.
        self.engine.query.side_effect = Exception("boom")
        try:
            self.skill.handle_search(_message({"word": "dog"}))
        except Exception as e:  # noqa: BLE001
            self.fail(f"handle_search must not let engine exceptions propagate: {e!r}")
        self.skill.speak_dialog.assert_called_once_with("no_answer")
        self.skill.speak.assert_not_called()


# ---------------------------------------------------------------------------
# "prev_word" follow-up context
# ---------------------------------------------------------------------------

class TestPrevWordContext(unittest.TestCase):

    def setUp(self):
        self.skill, self.engine = _make_skill()
        self.skill.speak = MagicMock()
        self.skill.speak_dialog = MagicMock()

    def _dispatch_and_capture(self, event, data, session):
        """Drive ``event`` through the real ``IntentDispatcher`` (the same
        §8 handler-lifecycle owner ovos-core wires up) and capture the
        session carried on ``ovos.intent.handler.complete`` — the §8
        terminal, which OVOS-SESSION-2 §2.6 has the orchestrator's
        completion sync (``IntentService._sync_handler_mutations``, the real
        production callback) fold the handler's ``intent_context`` write
        into before this terminal fires. This is the wire carrier of the
        handler's context write; the orchestrator's private
        ``SessionManager.sessions`` registry is never read directly, and
        ``mycroft.skill.handler.complete`` (ovos-workshop's own internal
        done-signal to ovos-core, never a spec topic) is only consumed by
        the dispatcher itself, exactly as in the real stack.
        """
        carried = {}

        def _on_complete(m):
            if m.context.get("session"):
                carried.update(m.context["session"])

        self.skill.bus.on("ovos.intent.handler.complete", _on_complete)
        dispatcher = IntentDispatcher(self.skill.bus, timeout=5,
                                      on_done_signal=lambda done, dispatch:
                                          IntentService._sync_handler_mutations(
                                              None, done, dispatch))
        msg = Message(f"{self.skill.skill_id}:{event}", data=data or {})
        msg.context["session"] = session.serialize()
        try:
            dispatcher.dispatch(msg, skill_id=self.skill.skill_id, intent_name=event)
        finally:
            dispatcher.shutdown()
        return carried

    def test_successful_lookup_sets_prev_word_context(self):
        self.engine.query.return_value = [("a loyal companion", 0.9)]
        session = Session("s1")
        carried = self._dispatch_and_capture("search_wordnet", {"word": "dog"}, session)
        stored = carried.get("intent_context", {}).get("prev_word")
        self.assertEqual(stored["value"], "dog")

    def test_failed_lookup_does_not_set_prev_word_context(self):
        self.engine.query.return_value = []
        session = Session("s2")
        carried = self._dispatch_and_capture("search_wordnet", {"word": "xyzzy"}, session)
        self.assertNotIn("prev_word", carried.get("intent_context", {}) or {})

    def test_blacklisted_slot_resolves_from_prev_word_context(self):
        session = Session("s3")
        session.set_intent_context("prev_word", "serendipity", scope="shared")
        self.engine.query.return_value = [("a fortunate accident", 0.9)]
        self.skill.handle_search(_message_with_session({"word": "it"}, session))
        self.skill.speak.assert_called_once_with("a fortunate accident")
        self.skill.speak_dialog.assert_not_called()
        self.engine.query.assert_called_once()
        args, _ = self.engine.query.call_args
        self.assertEqual(args[0], "serendipity")

    def test_empty_slot_without_context_still_reprompts(self):
        session = Session("s4")
        self.skill.handle_search(_message_with_session({"word": ""}, session))
        self.skill.speak_dialog.assert_called_once_with("unresolved")
        self.skill.speak.assert_not_called()


# ---------------------------------------------------------------------------
# Context-gated spell intent
# ---------------------------------------------------------------------------

class TestSpellWordIntent(unittest.TestCase):

    def setUp(self):
        self.skill, self.engine = _make_skill()
        self.skill.speak = MagicMock()
        self.skill.speak_dialog = MagicMock()

    def test_spells_word_from_prev_word_context(self):
        session = Session("spell-1")
        session.set_intent_context("prev_word", "cat", scope="shared")
        self.skill.handle_spell_word_intent(_message_with_session({}, session))
        self.skill.speak_dialog.assert_called_once_with(
            "spell.word", {"word": "cat", "letters": "C, A, T"})

    def test_reprompts_with_no_prev_word_context(self):
        session = Session("spell-2")
        self.skill.handle_spell_word_intent(_message_with_session({}, session))
        self.skill.speak_dialog.assert_called_once_with("unresolved")

    def test_spell_word_intent_file_has_no_word_slot(self):
        # spell_word.intent is gated on context, not a {word} slot - the
        # follow-up utterance itself never carries the word.
        for line in _lines("spell_word.intent"):
            self.assertNotIn("{word}", line)

    def test_spell_word_dialog_uses_word_and_letters(self):
        lines = _lines("spell.word.dialog")
        self.assertEqual(len(lines), 1)
        self.assertIn("{word}", lines[0])
        self.assertIn("{letters}", lines[0])


# ---------------------------------------------------------------------------
# Explicit intent — real skill, no mocked speak/speak_dialog
# ---------------------------------------------------------------------------

class TestHandleSearchNeverLeaksSkillError(unittest.TestCase):
    """End-to-end guard against the literal "skill.error" leak.

    Replays the exact dispatch path OVOS uses for a registered intent
    handler (``ovos_utils.events.create_wrapper`` wrapping the handler with
    the skill's own start/end/error callbacks, see
    ``OVOSSkill.add_event``/``_on_event_error``) so this test exercises the
    real framework fallback, not a mock of it. On the unfixed skill this
    fails: it captures a spoken utterance literally equal to "skill.error",
    because ``ovos_skill_wordnet`` ships no ``skill.error.dialog`` for any
    locale and ``handle_search`` let the engine exception escape.
    """

    def setUp(self):
        self.skill, self.engine = _make_skill()
        self.spoken = []
        self.skill.bus.on("speak", lambda m: self.spoken.append(m.data.get("utterance")))

    def _dispatch_through_real_wrapper(self, message):
        from ovos_utils.events import create_wrapper

        skill_data = {"name": "handle_search"}

        def on_start(msg):
            pass

        def on_end(msg):
            pass

        def on_error(error, msg):
            self.skill._on_event_error(str(error), msg, "handle_search",
                                       skill_data, speak_errors=True)

        wrapper = create_wrapper(self.skill.handle_search, self.skill.skill_id,
                                 on_start, on_end, on_error)
        wrapper(message)

    def test_engine_exception_never_speaks_literal_skill_error(self):
        self.engine.query.side_effect = Exception("boom")
        self._dispatch_through_real_wrapper(_message({"word": "dog"}))
        self.assertNotIn("skill.error", self.spoken,
                         f"leaked un-localized 'skill.error' literal: {self.spoken}")

    def test_engine_exception_speaks_real_no_answer_dialog(self):
        self.engine.query.side_effect = Exception("boom")
        self._dispatch_through_real_wrapper(_message({"word": "dog"}))
        no_answer_lines = _lines("no_answer.dialog")
        self.assertTrue(self.spoken, "handle_search spoke nothing on engine failure")
        self.assertIn(self.spoken[0], no_answer_lines,
                      f"expected a real no_answer.dialog line, got {self.spoken[0]!r}")


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


# ---------------------------------------------------------------------------
# Known gap: unresolved.dialog locale coverage
# ---------------------------------------------------------------------------

LOCALE_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "ovos_skill_wordnet", "locale",
)


class TestUnresolvedDialogLocaleCoverage(unittest.TestCase):
    """Tracks the known "unresolved" locale-coverage gap.

    handle_search speaks the "unresolved" dialog when the {word} slot is
    empty or anaphoric. Only en-US and da-DK ship a real unresolved.dialog;
    every other locale falls back to OVOS's missing-resource behavior, which
    is to speak the raw dialog id ("unresolved") verbatim rather than a
    sentence - not a crash, but still an un-localized string reaching the
    user, same failure shape as the "skill.error" leak this PR otherwise
    fixes.

    HARD RULE: no machine-translated locale drafts. So this gap is
    deliberately NOT closed by adding auto-translated unresolved.dialog
    files, and NOT closed by repointing the call at no_answer.dialog either
    - "no answer" and "I didn't understand which word" are different
    situations and conflating them would mislead the user about what went
    wrong. This test just locks down the current, known state so the gap
    is visible and doesn't silently grow (a locale added without
    unresolved.dialog support should show up here) or silently shrink via
    an unreviewed machine-translated file (a locale gaining the file
    without going through this test list should also show up here).
    """

    def _locales(self):
        return sorted(
            d for d in os.listdir(LOCALE_ROOT)
            if os.path.isdir(os.path.join(LOCALE_ROOT, d))
        )

    def test_unresolved_dialog_only_covers_en_and_da(self):
        covered = {
            loc for loc in self._locales()
            if os.path.isfile(os.path.join(LOCALE_ROOT, loc, "unresolved.dialog"))
        }
        self.assertEqual(
            covered, {"en-US", "da-DK", "kab"},
            "unresolved.dialog locale coverage changed - if this is a new "
            "human translation, update this test's expected set; if it's "
            "machine-translated, it violates the no-machine-translation "
            "rule and should not be merged"
        )

    def test_no_answer_dialog_covers_every_shipped_locale(self):
        # Sanity check for the *other* branch's fallback: no_answer.dialog
        # (spoken when the engine genuinely found nothing) must not have
        # the same gap "unresolved" does.
        locales = self._locales()
        missing = [
            loc for loc in locales
            if not os.path.isfile(os.path.join(LOCALE_ROOT, loc, "no_answer.dialog"))
        ]
        self.assertEqual(missing, [], f"no_answer.dialog missing for: {missing}")

    def test_unresolved_path_leaks_raw_dialog_id_outside_covered_locales(self):
        # Documents (does not fix - see class docstring) the literal-string
        # leak for the 29 locales without unresolved.dialog: OVOS's missing
        # resource behavior speaks the dialog id itself, not a sentence.
        skill, engine = _make_skill()
        with patch.object(type(skill), "lang", new_callable=lambda: property(lambda s: "de-DE")):
            captured = []
            skill.bus.on("speak", lambda m: captured.append(m.data.get("utterance")))
            skill.speak_dialog("unresolved")
            self.assertEqual(
                captured, ["unresolved"],
                "expected the known raw-dialog-id leak for de-DE (no "
                "unresolved.dialog shipped); if this now speaks a real "
                "sentence, a translation was added - update "
                "test_unresolved_dialog_only_covers_en_and_da's expected set"
            )


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
