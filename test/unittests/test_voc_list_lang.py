"""
``voc_list`` must honour the ``lang`` argument it is given instead of
always resolving vocabulary through the skill's own default language.
The skill's default is en-US; a caller asking ``voc_list`` for da-DK
vocabulary must get back da-DK strings, not the en-US ones.
"""
import unittest
from os.path import dirname

from ovos_utils.messagebus import FakeBus

import ovos_skill_wordnet
from ovos_skill_wordnet import WordnetSkill

DA_PRONOUNS = ["han", "ham", "hans", "hun", "hende", "hendes", "den", "det",
               "dens", "dets", "de", "dem", "deres"]
EN_PRONOUNS = ["he", "him", "his", "she", "her", "hers", "it", "its",
               "they", "them", "their", "theirs"]


class TestVocListLang(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.skill_id = "ovos-skill-wordnet.openvoiceos"
        cls.root_dir = dirname(ovos_skill_wordnet.__file__)

    def setUp(self):
        self.bus = FakeBus()
        self.skill = WordnetSkill()
        self.skill._startup(self.bus, self.skill_id)
        self.addCleanup(self.skill.default_shutdown)

    def test_voc_list_returns_requested_lang_vocab(self):
        self.assertEqual(self.skill.lang, "en-US")

        da_pronoun = self.skill.voc_list("pronoun", lang="da-DK")
        self.assertEqual(sorted(da_pronoun), sorted(DA_PRONOUNS))

        en_pronoun = self.skill.voc_list("pronoun", lang="en-US")
        self.assertEqual(sorted(en_pronoun), sorted(EN_PRONOUNS))

        self.assertNotEqual(sorted(da_pronoun), sorted(en_pronoun))

    def test_slot_blacklist_resolves_voc_reference_in_requested_lang(self):
        # word.blacklist only ships for en-US and pt-BR; pt-BR is the
        # non-default locale that exercises the <voc> resolution path.
        blacklist = self.skill._slot_blacklist("pt-BR")
        self.assertIn("ele", blacklist)
        self.assertIn("dela", blacklist)
        self.assertNotIn("he", blacklist)
        self.assertNotIn("she", blacklist)


if __name__ == "__main__":
    unittest.main()
