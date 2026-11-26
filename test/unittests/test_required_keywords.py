"""Every locale that ships search_wordnet.intent also ships search_wordnet.required,
and every golden positive for that intent names one of its keywords."""
import json
from pathlib import Path

import pytest
from ovos_spec_tools import utterance_contains

ROOT = Path(__file__).resolve().parents[2]
LOCALE_DIR = ROOT / "ovos_skill_wordnet" / "locale"
GOLDEN_DIR = ROOT / "test" / "end2end"
INTENT = "search_wordnet"

LOCALES = sorted(p.parent.name for p in LOCALE_DIR.glob(f"*/{INTENT}.intent"))
# Chinese and Japanese write the service name with no space before the next
# word, so no keyword occurs in these rows as a whole word (OVOS-INTENT-2 4.3).
ROWS_REJECTED_BY_REQUIRED = {
    "cmn-CN": {"在WordNet中搜索同义词", "问WordNet关于反义词", "在WordNet中搜索上位词"},
    "ja-JP": {"WordNetで類義語を検索して", "WordNetに対義語について聞いて", "WordNetで反意語を検索して"},
}


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
    keywords = _keywords(lang)
    golden = GOLDEN_DIR / f"golden_utterances_{lang}.jsonl"
    rows = [json.loads(ln) for ln in golden.read_text(encoding="utf-8").splitlines()
            if ln.strip()]
    missing = {r["utterance"] for r in rows
               if r["intent_label"].removesuffix(".intent") == INTENT
               and not utterance_contains(r["utterance"], keywords)}
    assert missing == ROWS_REJECTED_BY_REQUIRED.get(lang, set()), (
        f"{lang}: golden rows without a required keyword: {sorted(missing)}")
