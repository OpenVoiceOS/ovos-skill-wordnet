"""Multilingual golden-utterance end-to-end coverage for ovos-skill-wordnet.

test_golden_utterances.py only exercises en-US via a single shared
MiniCroft. Every locale under locale/ ships a real search_wordnet.intent
template file plus a wordnet_query.voc; this suite gives each of them a
golden row set derived mechanically from that locale's own files (see
golden_utterances_<lang>.jsonl and the generator that produced them).

Booting one shared MiniCroft with every locale as a secondary_lang hits a
known ovoscope harness bug (get_minicroft cannot reliably train that many
secondary-lang pipelines; see the alerts skill's
test_golden_utterances_multilang.py, which is skipped on dev for exactly
this reason). Instead, this suite boots one MiniCroft PER LOCALE in turn
(same pattern as ovos-skill-date-time's test_intents_it_it.py:
get_minicroft([SKILL_ID], max_wait=150, lang=LANG)), runs every row for
that locale against it, then tears it down before moving to the next
locale. One test item per locale keeps the boot cost to one MiniCroft per
locale rather than one per row.
"""
import json
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-wordnet.openvoiceos"

_PIPELINE = [
    "ovos-padacioso-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-medium",
    "ovos-padacioso-pipeline-plugin-low",
]

_IGNORE = [
    "speak",
    "ovos.utterance.speak",
    "mycroft.audio.play_sound",
]

END2END_DIR = Path(__file__).parent

# cmn-CN and ja-JP are gaps, not covered here: on the GitHub Actions CI
# runner (gh-automations ovoscope workflow, pytest-xdist "auto" workers)
# every row for both locales routes to "complete_intent_failure" with no
# prior pipeline match log line at all -- the utterance never reaches
# search_wordnet.intent's own matcher. This does not reproduce in a local
# clone with the identical installed package set, serially or under
# `pytest -n auto`, so it is not a template defect or a padacioso matching
# gap in this skill; it points at a CI-runner-specific difference in how
# CJK-script utterances are tokenized/segmented before intent matching.
# See knowledge/wiki/audits/skills-qa/golden-all-locales-batchF.md for the
# full finding.
LANGS = [
    "ar-XX", "bg-BG", "ca-ES", "da-DK", "de-DE", "el-GR",
    "en-US", "es-ES", "eu-ES", "fi-FI", "fr-FR", "gl-ES", "he-IL",
    "hr-HR", "id-ID", "is-IS", "it-IT", "kab", "lt-LT",
    "nb-NO", "nl-NL", "nn-NO", "pl-PL", "pt-BR", "pt-PT", "ro-RO",
    "sk-SK", "sl-SI", "sv-SE", "th-TH", "zsm-MY",
]


def _matches_intent(msg_type: str, skill_id: str, intent_label: str) -> bool:
    prefix = f"{skill_id}:"
    if not msg_type.startswith(prefix):
        return False
    observed = msg_type[len(prefix):]
    observed_base = observed.rsplit(".", 1)[0] if observed.endswith(".intent") else observed
    expected_base = intent_label.rsplit(".", 1)[0] if intent_label.endswith(".intent") else intent_label
    return observed_base == expected_base


def _load_rows(lang):
    path = END2END_DIR / f"golden_utterances_{lang}.jsonl"
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("needs_manual"):
                continue
            rows.append(row)
    return rows


def _types(mc, text, lang, session_id):
    session = Session(session_id)
    session.lang = lang
    session.pipeline = list(_PIPELINE)
    session.blacklisted_intents = []
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": lang},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(
        mc,
        eof_msgs=["mycroft.skill.handler.start", "ovos.intent.unmatched"],
        ignore_messages=_IGNORE,
    )
    capture.capture(utterance, timeout=30)
    return [m.msg_type for m in capture.finish()]


@pytest.fixture(params=LANGS)
def locale_minicroft(request):
    lang = request.param
    mc = get_minicroft([SKILL_ID], max_wait=150, lang=lang)
    yield lang, mc
    mc.stop()


@pytest.mark.timeout(300)
def test_golden_utterances_per_locale(locale_minicroft):
    lang, mc = locale_minicroft
    rows = _load_rows(lang)
    assert rows, f"no golden rows loaded for {lang}"
    failures = []
    for row in rows:
        types = _types(mc, row["utterance"], lang, f"golden-{lang}-{row['utterance']}")
        if not any(_matches_intent(t, SKILL_ID, row["intent_label"]) for t in types):
            failures.append(
                f"{row['utterance']!r}: expected {SKILL_ID}:{row['intent_label']}, got {types!r}"
            )
    assert not failures, "\n".join(failures)
