"""The carrier templates are a spec `.intent` file that no handler registers.

OVOS-INTENT-2 §1 defines seven resource roles and `.list` is not one, so the
templates ship as `query_templates.intent` and are read, never routed.
"""
import ast
import re
import unittest
from pathlib import Path

import ovos_skill_wordnet as module
from ovos_skill_wordnet import WordnetSkill
from types import SimpleNamespace

SKILL_DIR = Path(__file__).resolve().parents[2] / "ovos_skill_wordnet"
LOCALE_ROOT = SKILL_DIR / "locale"


def _extract(utterance, lang):
    module.__file__ = str(SKILL_DIR / "__init__.py")
    fake = SimpleNamespace(_template_cache={})
    fake._query_templates = lambda l: WordnetSkill._query_templates(fake, l)
    return WordnetSkill.extract_term(fake, utterance, lang)


def _registered_intents():
    """Intent names the skill registers, read from its @intent_handler calls."""
    tree = ast.parse((SKILL_DIR / "__init__.py").read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "intent_handler"):
            names.update(a.value for a in node.args
                         if isinstance(a, ast.Constant) and isinstance(a.value, str))
    return names


class TestQueryTemplatesResource(unittest.TestCase):
    def test_no_list_file_ships(self):
        self.assertEqual([], sorted(p.relative_to(LOCALE_ROOT).as_posix()
                                    for p in LOCALE_ROOT.rglob("*.list")))

    def test_every_template_locale_ships_an_intent_file(self):
        shipped = sorted(p.parent.name for p in LOCALE_ROOT.glob("*/query_templates.intent"))
        self.assertEqual(["en-US", "kab", "pt-BR"], shipped)

    def test_define_stoic_yields_stoic(self):
        raw = (LOCALE_ROOT / "en-US" / "query_templates.intent").read_text(encoding="utf-8")
        line = next(l.strip() for l in raw.splitlines() if l.strip() == "define {word}")
        utterance = line.replace("{word}", "stoic")
        self.assertEqual("define stoic", utterance)
        self.assertEqual("stoic", _extract(utterance, "en-US"))
        self.assertEqual("stoic", _extract("define stoic", "en-US"))

    def test_templates_are_not_registered_as_an_intent(self):
        registered = _registered_intents()
        self.assertTrue(registered, "no @intent_handler found")
        self.assertFalse({n for n in registered if re.search(r"query_templates", n)})
        shipped = {p.stem for p in LOCALE_ROOT.rglob("*.intent")}
        self.assertEqual({"query_templates"}, shipped - {n.removesuffix(".intent") for n in registered})


if __name__ == "__main__":
    unittest.main()
