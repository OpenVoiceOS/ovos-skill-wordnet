"""Golden-utterance end-to-end coverage for ovos-skill-wordnet (en-US).

The golden corpus (``golden_utterances.jsonl``) is a vendored slice of the
shared ovoscope golden-utterance dataset, keyed by
``skill_id == "ovos-skill-wordnet.openvoiceos"`` (matches this skill's real
OPM entry point too). One shared ``MiniCroft`` (module-scoped fixture) is
booted for the whole suite; every row is its own parametrized test item.

The WordNet backend is fully offline (local corpus via
``ovos-wordnet-plugin``, ``runtime_requirements.requires_internet=False``),
but ``engine.query``/``engine.get_definition`` are still stubbed for
determinism, same as ``test_intents_en_us.py``. Unlike ovos-skill-wolfie,
``can_answer``/the fallback handler gate on a specific ``WordnetQuery`` vocab
match rather than "any word with a definition", so they're much less likely
to over-claim negatives -- but the stub keeps the suite from depending on
what words are actually in the bundled WordNet corpus.
"""
import json
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-wordnet.openvoiceos"
LANG = "en-US"

_PIPELINE = [
    "ovos-padatious-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-high",
    "ovos-padatious-pipeline-plugin-medium",
    "ovos-padacioso-pipeline-plugin-medium",
    "ovos-fallback-pipeline-plugin-high",
    "ovos-fallback-pipeline-plugin-medium",
]

_IGNORE = [
    "speak",
    "ovos.utterance.speak",
    "mycroft.audio.play_sound",
]

GOLDEN_PATH = Path(__file__).parent / "golden_utterances.jsonl"

# utterances lifted verbatim from OTHER skills' golden-utterance slices in
# the shared ovoscope corpus, picked for lexical overlap with wordnet's
# "ask"/"search ... for"/"what does ... say about" vocabulary.
NEGATIVE_UTTERANCES = [
    ("can you tell me the weather", "ovos-skill-weather.openvoiceos"),
    ("tell me the word of the day", "ovos-skill-word-of-the-day.openvoiceos"),
    ("search wikihow for something", "ovos-skill-wikihow.openvoiceos"),
    ("can you spell word", "ovos-skill-spelling.openvoiceos"),
    ("set an alarm", "ovos-skill-alerts.openvoiceos"),
    ("tell me a joke", "ovos-skill-icanhazdadjokes.openvoiceos"),
]

# wolfie/wikipedia/wordnet cross-arbitration: real wolfie/wikipedia corpus
# utterances fired against THIS skill (the third leg of the highest-theft-
# risk trio in this campaign), documenting and asserting wordnet does not
# claim them.
TRIO_ARBITRATION = [
    ("ask the wolf something", "ovos-skill-wolfie.openvoiceos"),
    ("search the wolf for something", "ovos-skill-wolfie.openvoiceos"),
    ("can you find something on wiki", "ovos-skill-wikipedia.openvoiceos"),
    ("check wikipedia for something", "ovos-skill-wikipedia.openvoiceos"),
]

# Real, CI-observed collision: en-US/search_wordnet.intent's
# "search (word net|wordnet) for {word}" template requires the literal
# "word net"/"wordnet" token, but padatious's fuzzy matcher can claim
# "search the wolf for something" (a real wolfie corpus utterance) for
# wordnet via bag-of-words overlap on the "search ... for" phrase SHAPE
# alone, with no "wordnet" token anywhere in the utterance. This does NOT
# reproduce locally (no libfann-dev/sudo here to build ovos-padatious, so
# padacioso -- a stricter, non-fuzzy matcher -- handles it and correctly
# does not claim it).
#
# Confirmed genuinely NON-DETERMINISTIC across separate CI runs on this PR
# with no code changes between them: run 1 the collision reproduced
# (XFAIL, as expected); run 2, moments later, it did NOT (XPASS, failing
# the strict xfail). padatious's own matching is known to vary run-to-run
# in this ecosystem (fuzzy scoring, not a fixed grammar), so a
# strict=True xfail is the wrong tool here -- it would flip the CI result
# on unrelated re-runs with no code change either way. Using strict=False
# instead: the row is expected to sometimes fail (documented, tracked,
# same root cause as the sibling ovos-skill-spelling and
# ovos-skill-wikipedia PRs' "search ... for" collisions) without making
# CI flaky. The sibling "ask the wolf something" / "ask (word net|wordnet)
# about {word}" pair does NOT collide (confirmed both directly and via an
# earlier draft of this PR that incorrectly xfailed it too and caught the
# XPASS).
_TRIO_XFAIL_REASONS = {
    "search the wolf for something": (
        "padatious can fuzzy-match this to search_wordnet.intent via "
        "bag-of-words overlap on the 'search ... for {word}' phrase shape, "
        "with no 'wordnet' token anywhere in the utterance; confirmed "
        "non-deterministic across separate CI-pinned-padatious runs (not "
        "reproducible under the padacioso fallback used in this dev venv) "
        "-- see the PR description."
    ),
}

try:
    import ovos_padatious  # noqa: F401
    _PADATIOUS_INSTALLED = True
except ImportError:
    _PADATIOUS_INSTALLED = False


def _as_trio_param(case):
    text, _claimant = case
    reason = _TRIO_XFAIL_REASONS.get(text)
    if reason is None or not _PADATIOUS_INSTALLED:
        return pytest.param(case, id=text)
    # strict=False: see the long comment above -- this specific collision
    # is confirmed non-deterministic run-to-run under real padatious, so a
    # strict xfail would itself be a flaky-CI source.
    return pytest.param(case, id=text, marks=pytest.mark.xfail(reason=reason, strict=False))


TRIO_PARAMS = [_as_trio_param(c) for c in TRIO_ARBITRATION]


def _matches_intent(msg_type: str, skill_id: str, intent_label: str) -> bool:
    """Tolerant matcher, same shape as the sibling repos' suites."""
    prefix = f"{skill_id}:"
    if not msg_type.startswith(prefix):
        return False
    observed = msg_type[len(prefix):]
    observed_base = observed.rsplit(".", 1)[0] if observed.endswith(".intent") else observed
    expected_base = intent_label.rsplit(".", 1)[0] if intent_label.endswith(".intent") else intent_label
    return observed_base == expected_base


_XFAIL_REASONS = {}


def _load_golden_rows():
    rows = []
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("needs_manual"):
                continue
            rows.append(row)
    return rows


def _as_param(row):
    reason = _XFAIL_REASONS.get(row["utterance"])
    if reason is None:
        return pytest.param(row, id=row["utterance"])
    return pytest.param(row, id=row["utterance"], marks=pytest.mark.xfail(reason=reason, strict=True))


GOLDEN_ROWS = [_as_param(r) for r in _load_golden_rows()]


@pytest.fixture(scope="module")
def minicroft():
    mc = get_minicroft([SKILL_ID])
    skill = mc.plugin_skills[SKILL_ID].instance
    skill.engine.query = lambda *a, **k: [("a stubbed definition", 0.9)]
    skill.engine.get_definition = lambda *a, **k: "a stubbed definition"
    yield mc
    mc.stop()


def _types(mc, text, session_id):
    session = Session(session_id)
    session.lang = LANG
    session.pipeline = list(_PIPELINE)
    # blacklisted_intents defaults to None on a fresh Session, which crashes
    # the padacioso pipeline (NoneType membership test) - force an empty list.
    session.blacklisted_intents = []
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": LANG},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(
        mc,
        # ``ovos.intent.unmatched`` catches the no-match path; the matched
        # path needs no extra eof topic here — ``terminal_signals`` (default
        # True) already merges the universal §9.5 ``ovos.utterance.handled``
        # end-marker in, which fires once for every utterance's lifecycle
        # regardless of outcome. ``mycroft.skill.handler.start`` is an
        # ovos-workshop-internal signal to ovos-core, never a spec topic.
        eof_msgs=["ovos.intent.unmatched"],
        ignore_messages=_IGNORE,
    )
    capture.capture(utterance, timeout=30)
    return [m.msg_type for m in capture.finish()]


def _golden_id(row):
    return row["utterance"]


@pytest.mark.timeout(60)
@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=_golden_id)
def test_golden_utterance(minicroft, row):
    types = _types(minicroft, row["utterance"], f"golden-{_golden_id(row)}")
    assert any(_matches_intent(t, SKILL_ID, row["intent_label"]) for t in types), (
        f"{row['utterance']!r}: expected {SKILL_ID}:{row['intent_label']}, got {types!r}"
    )


@pytest.mark.timeout(60)
@pytest.mark.parametrize("negative", NEGATIVE_UTTERANCES, ids=lambda n: n[0])
def test_negative_confusable_not_claimed(minicroft, negative):
    text, source_skill = negative
    types = _types(minicroft, text, f"negative-{text}")
    claimed = any(t.startswith(f"{SKILL_ID}:") for t in types)
    assert not claimed, f"{text!r} (from {source_skill}) was incorrectly claimed by {SKILL_ID}"


@pytest.mark.timeout(60)
@pytest.mark.parametrize("case", TRIO_PARAMS)
def test_trio_arbitration_not_claimed_by_wordnet(minicroft, case):
    text, expected_claimant = case
    assert expected_claimant != SKILL_ID, "this list is for utterances belonging to the OTHER two skills"
    types = _types(minicroft, text, f"trio-{text}")
    claimed = any(t.startswith(f"{SKILL_ID}:") for t in types)
    assert not claimed, (
        f"{text!r} (expected to belong to {expected_claimant}) was incorrectly claimed by {SKILL_ID}"
    )
