"""Every locale that ships search_wordnet.intent also ships search_wordnet.required,
and every golden positive for that intent names one of its keywords."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LOCALE_DIR = ROOT / "ovos_skill_wordnet" / "locale"
GOLDEN_DIR = ROOT / "test" / "end2end"
INTENT = "search_wordnet"

LOCALES = sorted(p.parent.name for p in LOCALE_DIR.glob(f"*/{INTENT}.intent"))


def _keywords(lang):
    path = LOCALE_DIR / lang / f"{INTENT}.required"
    return [ln.strip().casefold()
            for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]


def test_locales_found():
    assert LOCALES


@pytest.mark.parametrize("lang", LOCALES)
def test_required_file_is_not_empty(lang):
    assert _keywords(lang), f"{lang}: {INTENT}.required missing or empty"


@pytest.mark.parametrize("lang", LOCALES)
def test_required_lines_are_slot_free(lang):
    for keyword in _keywords(lang):
        assert "{" not in keyword and "}" not in keyword, f"{lang}: {keyword!r}"


@pytest.mark.parametrize("lang", LOCALES)
def test_golden_positives_name_a_keyword(lang):
    # Substring check: Japanese, Chinese and Thai write no spaces between words.
    keywords = _keywords(lang)
    golden = GOLDEN_DIR / f"golden_utterances_{lang}.jsonl"
    rows = [json.loads(ln) for ln in golden.read_text(encoding="utf-8").splitlines()
            if ln.strip()]
    missing = [r["utterance"] for r in rows
               if r["intent_label"].removesuffix(".intent") == INTENT
               and not any(k in r["utterance"].casefold() for k in keywords)]
    assert not missing, f"{lang}: golden rows without a required keyword: {missing}"
