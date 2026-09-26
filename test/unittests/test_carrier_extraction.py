"""The carrier phrasings must still be ANSWERED, not merely claimed.

`define stoic` used to be a line of `search_wordnet.intent`, and the intent
match was the only stage that separated the carrier from the term: the handler
received {word}="stoic" and looked THAT up. Now the intent holds only sentences
that name WordNet, so the phrasing reaches the fallback whole.

Measured against the real engine, that difference is the whole defect:

    engine.get_definition("stoic")        -> "a member of the ancient Greek ..."
    engine.get_definition("define stoic") -> None

So a test that asserts `can_answer` is true proves nothing about whether the
user hears an answer. These run the REAL WordNet engine and assert the
definition comes back.
"""
import os
import unittest
from types import SimpleNamespace

from ovos_wordnet_plugin import WordnetRetrievalEngine

import ovos_skill_wordnet as module
from ovos_skill_wordnet import WordnetSkill

# test/unittests/<this file> -> unittests -> test -> repo root: three levels,
# not two. Two lands on test/, where there is no locale/ directory, and every
# extraction then silently returns the utterance unchanged.
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# every phrasing removed from en-US search_wordnet.intent, with the term the
# carrier wraps
EN_US_FORMS = [
    ("define ephemeral", "ephemeral"),
    ("describe serendipity", "serendipity"),
    ("what does serendipity mean", "serendipity"),
    ("what does ibm stand for", "ibm"),
    ("what is a pangolin", "pangolin"),
    ("what is the definition of stoic", "stoic"),
    ("meaning of stoic", "stoic"),
    ("what is the synonym of happy", "happy"),
    ("antonyms of happy", "happy"),
]

# WordNet has no entry for "ibm". It had none before this change either: the
# intent bound {word}="ibm" and the handler looked up "ibm" and got nothing, so
# the user heard no definition then and hears none now. It is listed here to
# keep the extraction asserted for it while not claiming an answer that the
# corpus cannot give.
NO_CORPUS_ENTRY = {"ibm"}


def _extractor(lang_dir_owner=module):
    fake = SimpleNamespace(_template_cache={})
    fake._query_templates = lambda lang: WordnetSkill._query_templates(fake, lang)
    return lambda utterance, lang: WordnetSkill.extract_term(fake, utterance, lang)


class TestCarrierExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        module.__file__ = os.path.join(SKILL_DIR, "ovos_skill_wordnet",
                                       "__init__.py")
        cls.extract = staticmethod(_extractor())
        cls.engine = WordnetRetrievalEngine()

    def test_every_removed_form_yields_its_term(self):
        for utterance, term in EN_US_FORMS:
            with self.subTest(utterance=utterance):
                self.assertEqual(
                    term, self.extract(utterance, "en-US"),
                    f"the carrier was not stripped from {utterance!r}, so the "
                    f"engine is asked the whole sentence and answers nothing")

    def test_every_removed_form_is_answered_by_the_real_engine(self):
        """The assertion that `can_answer` cannot make."""
        for utterance, term in EN_US_FORMS:
            if term in NO_CORPUS_ENTRY:
                continue
            with self.subTest(utterance=utterance):
                defn = self.engine.get_definition(
                    self.extract(utterance, "en-US"), lang="en")
                self.assertTrue(
                    defn,
                    f"{utterance!r} extracted to {term!r} and the engine "
                    f"returned nothing; the user hears no definition")

    def test_the_carrier_is_what_breaks_the_lookup(self):
        """The control: without extraction these same forms answer nothing.

        Without this pair the test above could pass on an engine that answers
        anything at all, and would not show that the extraction is what fixed
        it.
        """
        answered_raw = [u for u, t in EN_US_FORMS
                        if t not in NO_CORPUS_ENTRY
                        and self.engine.get_definition(u, lang="en")]
        self.assertEqual(
            [], answered_raw,
            "these carrier phrases answered without extraction, so this "
            "suite is not measuring what it claims")

    def test_an_uncovered_phrasing_passes_through_unchanged(self):
        """A phrasing no template covers must not be mangled."""
        for utterance in ("stoic", "tell me about otters", ""):
            with self.subTest(utterance=utterance):
                self.assertEqual(utterance, self.extract(utterance, "en-US"))

    def test_a_bare_primary_subtag_resolves_the_locale(self):
        """`en` must find locale/en-US, as the resource loader does."""
        self.assertEqual("stoic", self.extract("define stoic", "en"))


class TestOtherLocalesShipTemplates(unittest.TestCase):
    """pt-BR and kab still carry the carrier lines in their intent.

    Their templates ship anyway, so the extraction is already in place when
    those lines are removed (T-5232) and there is no window where the locale
    claims the question and answers nothing.
    """

    def setUp(self):
        module.__file__ = os.path.join(SKILL_DIR, "ovos_skill_wordnet",
                                       "__init__.py")
        self.extract = _extractor()

    def test_pt_br_strips_its_carrier(self):
        self.assertEqual("efemero", self.extract("defina efemero", "pt-BR"))

    def test_kab_strips_its_carrier(self):
        self.assertEqual("awal", self.extract("glem awal", "kab"))


class TestDoubledSpacesInsideTheCarrier(unittest.TestCase):
    """A doubled space between the carrier's own words must still match.

    `re.escape` on the whole carrier made each internal space one literal
    space, so a doubled space inside the carrier matched nothing and the
    utterance passed through unchanged. Doubling AROUND the carrier always
    worked, because the pattern's own `\\s+` absorbs it.
    """

    def setUp(self):
        module.__file__ = os.path.join(SKILL_DIR, "ovos_skill_wordnet",
                                       "__init__.py")
        self.extract = _extractor()

    def test_a_doubled_space_inside_a_multi_word_carrier(self):
        self.assertEqual(
            "stoic",
            self.extract("what  is  the  definition  of  stoic", "en-US"))

    def test_a_single_space_carrier_still_matches(self):
        """The control: the case that already worked must not move."""
        self.assertEqual(
            "stoic",
            self.extract("what is the definition of stoic", "en-US"))

    def test_a_phrasing_with_no_carrier_is_still_unchanged(self):
        """The control in the other direction: the default is passthrough."""
        self.assertEqual("stoic", self.extract("stoic", "en-US"))


if __name__ == "__main__":
    unittest.main()
