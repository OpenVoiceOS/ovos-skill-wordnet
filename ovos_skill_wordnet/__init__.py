# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import re
from typing import Optional, Set, Tuple

from ovos_bus_client.message import Message
from ovos_bus_client.session import SessionManager
from ovos_utils.process_utils import RuntimeRequirements
from ovos_wordnet_plugin import WordnetRetrievalEngine
from ovos_spec_tools import expand
from ovos_workshop.decorators import intent_handler, common_query, fallback_handler
from ovos_workshop.resource_files import locate_lang_directories
from ovos_workshop.skills.fallback import FallbackSkill


def _literal(text: str) -> str:
    """The carrier's words as a pattern whose gaps take any run of whitespace.

    `re.escape` on the whole phrase makes each internal space one literal
    space, so "erzahl  mir  von X" with a doubled space inside the carrier
    matched nothing and fell through to the unchanged utterance. The words are
    escaped one by one and joined with `\\s+` instead.
    """
    return r"\s+".join(re.escape(word) for word in text.split())


class WordnetSkill(FallbackSkill):
    """Voice interface to WordNet via ovos-wordnet-plugin."""

    @property
    def runtime_requirements(self):
        return RuntimeRequirements(
            internet_before_load=False,
            network_before_load=False,
            requires_internet=False,
            requires_network=False,
            no_internet_fallback=True,
            no_network_fallback=True,
        )

    def initialize(self) -> None:
        self.engine = WordnetRetrievalEngine(config=dict(self.settings))
        self._template_cache = {}

    def _slot_blacklist(self, lang: str) -> Set[str]:
        """Return the values that may not fill the {word} slot for ``lang``.

        Reads ``word.blacklist`` and resolves any ``<voc>`` reference to the
        matching vocabulary file, so an anaphoric pronoun (or bare determiner)
        cannot be looked up as if it were a dictionary word.
        """
        path = self.find_resource("word.blacklist", lang=lang)
        if not path:
            return set()
        terms: Set[str] = set()
        with open(path) as blacklist:
            for line in blacklist:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                voc = re.match(r"^<(.+)>$", line)
                if voc:
                    terms.update(v.lower() for v in self.voc_list(voc.group(1), lang=lang))
                else:
                    terms.add(line.lower())
        return terms

    # ------------------------------------------------------------------
    # Carrier-phrase extraction
    # ------------------------------------------------------------------

    def _query_templates(self, lang: str) -> list:
        """The locale's carrier phrasings, as compiled extraction patterns.

        `define {word}` used to be a line of `search_wordnet.intent`, and the
        intent match was the only stage that ever separated the carrier from
        the term: the handler received {word}="stoic" and looked THAT up. The
        intent now holds only sentences that name WordNet, so those phrasings
        arrive here whole, and the engine answers `stoic` while it answers
        nothing at all for `define stoic`.

        The removed lines are therefore shipped as
        `locale/<lang>/query_templates.list` and reused here to strip the
        carrier. The locale directory is resolved the way the resource loader
        resolves it: `self.lang` normalises case and separator but does not add
        a region, so a hand-built `locale/{lang}` path misses `locale/en-US`
        for a session asking in `en`.
        """
        cached = self._template_cache.get(lang)
        if cached is not None:
            return cached

        patterns = []
        for directory in locate_lang_directories(lang, os.path.dirname(__file__)):
            path = directory / "query_templates.list"
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "{word}" not in line:
                    continue
                for variant in expand(line):
                    # one slot, and the carrier around it is literal text
                    head, _, tail = variant.partition("{word}")
                    patterns.append(re.compile(
                        r"^\s*" + _literal(head) + r"\s+(?P<word>.+?)\s*"
                        + (r"\s+" + _literal(tail) if tail.strip() else "")
                        + r"[\s?.!]*$", re.IGNORECASE))
            break  # the first directory that HAS a template file

        # longest carrier first: "what is the definition of X" must win over
        # "what is a X" when both could match
        patterns.sort(key=lambda p: -len(p.pattern))
        self._template_cache[lang] = patterns
        return patterns

    def extract_term(self, utterance: str, lang: str) -> str:
        """Return the term a carrier phrase wraps, or the utterance unchanged.

        Unchanged is the right default: a phrasing no template covers is passed
        through exactly as it was before this method existed, so adding the
        extraction cannot make a working lookup stop working.
        """
        for pattern in self._query_templates(lang):
            found = pattern.match(utterance)
            if found:
                term = found.group("word").strip()
                if term:
                    return term
        return utterance

    # ------------------------------------------------------------------
    # Common Query pipeline
    # ------------------------------------------------------------------

    @common_query()
    def match_common_query(self, phrase: str, lang: str) -> Tuple[Optional[str], float]:
        short = lang.split("-")[0]
        defn = self.engine.get_definition(self.extract_term(phrase, lang),
                                          lang=short)
        if defn:
            return defn, 0.6
        return None, 0.0

    # ------------------------------------------------------------------
    # Explicit intent
    # ------------------------------------------------------------------

    @intent_handler("search_wordnet.intent")
    def handle_search(self, message):
        # {word} is left unresolved (no key at all) when the utterance's slot
        # value is excluded by the matcher itself, same as an explicit
        # anaphoric blacklist hit below — both re-prompt instead of crashing.
        query = message.data.get("word", "")
        lang = self.lang
        if not query.strip() or query.strip().lower() in self._slot_blacklist(lang):
            # anaphoric slot value: leave {word} unresolved so a later stage
            # can supply the referent active in the conversation
            #
            # KNOWN GAP: "unresolved" ("I did not catch which word you
            # mean") only ships for en-US and da-DK. It is intentionally
            # NOT "no_answer" ("word net does not know the answer") - that
            # dialog means WordNet has no definition for a word it did
            # understand, which is a different situation from never having
            # understood which word was meant, and speaking it here would
            # actively mislead the user about what went wrong. Until a human
            # translator supplies the missing unresolved.dialog for the
            # other 29 shipped locales, this path speaks the raw dialog id
            # ("unresolved") in those locales rather than a sentence -
            # tracked by test_unresolved_dialog_only_covers_en_and_da below,
            # not silently patched over with a machine translation.
            self.speak_dialog("unresolved")
            return
        # Mirror handle_fallback's try/except: an uncaught exception here
        # (e.g. the underlying wn sqlite connection racing with a concurrent
        # common_qa lookup on another thread) would otherwise propagate out
        # of this @intent_handler. The framework's generic error path then
        # tries to speak a "skill.error" dialog this skill never ships, and
        # falls back to speaking that literal, un-localized string. Speaking
        # "no_answer" here keeps every failure mode inside real, localized
        # dialog.
        try:
            results = self.engine.query(query, lang=lang, k=1)
        except Exception:
            self.log.exception("WordnetSkill: engine.query failed for %r", query)
            results = []
        if results:
            self.speak(results[0][0])
        else:
            self.speak_dialog("no_answer")

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    def can_answer(self, message: Message) -> bool:
        # Wordnet only answers definition-shaped questions, so the ping applies
        # the same vocab guard the handler does. The lookup itself is left to
        # the handler.
        utterance = message.data["utterances"][0]
        return self.voc_match(utterance, "wordnet_query",
                              lang=SessionManager.get(message).lang)

    @fallback_handler(priority=90)
    def handle_fallback(self, message):
        utterance = message.data.get("utterance", "")
        sess = SessionManager.get(message)
        lang = sess.lang

        if not self.voc_match(utterance, "wordnet_query", lang=lang):
            return False

        try:
            results = self.engine.query(self.extract_term(utterance, lang),
                                        lang=lang, k=1)
        except Exception:
            return False
        if results:
            self.speak(results[0][0])
            return True
        return False
