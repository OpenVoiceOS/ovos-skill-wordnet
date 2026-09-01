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
import re
from typing import Optional, Set, Tuple

from ovos_bus_client.message import Message
from ovos_bus_client.session import SessionManager
from ovos_utils.process_utils import RuntimeRequirements
from ovos_wordnet_plugin import WordnetRetrievalEngine
from ovos_workshop.decorators import intent_handler, common_query, fallback_handler
from ovos_workshop.skills.fallback import FallbackSkill


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
    # Common Query pipeline
    # ------------------------------------------------------------------

    @common_query()
    def match_common_query(self, phrase: str, lang: str) -> Tuple[Optional[str], float]:
        short = lang.split("-")[0]
        defn = self.engine.get_definition(phrase, lang=short)
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
        return self.voc_match(utterance, "WordnetQuery",
                              lang=SessionManager.get(message).lang)

    @fallback_handler(priority=90)
    def handle_fallback(self, message):
        utterance = message.data.get("utterance", "")
        sess = SessionManager.get(message)
        lang = sess.lang

        if not self.voc_match(utterance, "WordnetQuery", lang=lang):
            return False

        try:
            results = self.engine.query(utterance, lang=lang, k=1)
        except Exception:
            return False
        if results:
            self.speak(results[0][0])
            return True
        return False
