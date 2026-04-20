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
import random
from typing import Optional, Tuple

from ovos_utils.process_utils import RuntimeRequirements
from ovos_wordnet_plugin import NOUN, ADJ, VERB, Wordnet, WordnetRetrievalEngine
from ovos_workshop.decorators import intent_handler, common_query
from ovos_workshop.skills.ovos import OVOSSkill


class WordnetSkill(OVOSSkill):
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

    def _word_data(self, word: str, lang: str) -> dict:
        for pos in (NOUN, ADJ, VERB):
            data = Wordnet.get(word, pos=pos, lang=lang)
            if data:
                return data
        return {}

    @common_query()
    def match_common_query(self, phrase: str, lang: str) -> Tuple[Optional[str], float]:
        short = lang.split("-")[0]
        defn = self.engine.get_definition(phrase, lang=short)
        if defn:
            return defn, 0.6
        return None, 0.0

    @intent_handler("search_wordnet.intent")
    def handle_search(self, message):
        self.handle_definition(message)

    @intent_handler("definition.intent")
    def handle_definition(self, message):
        query = message.data["query"]
        lang = self.lang.split("-")[0]
        defn = self.engine.get_definition(query, lang=lang)
        if defn:
            self.speak(defn)
        else:
            self.speak_dialog("no_answer")

    @intent_handler("lemma.intent")
    def handle_lemma(self, message):
        query = message.data["query"]
        lang = self.lang.split("-")[0]
        items = [w for w in (self._word_data(query, lang).get("lemmas") or [])
                 if w.lower() != query.lower()]
        if items:
            self.speak(random.choice(items))
        else:
            self.speak_dialog("no_answer")

    @intent_handler("antonym.intent")
    def handle_antonym(self, message):
        query = message.data["query"]
        lang = self.lang.split("-")[0]
        items = self._word_data(query, lang).get("antonyms") or []
        if items:
            self.speak(random.choice(items))
        else:
            self.speak_dialog("no_answer")

    @intent_handler("holonym.intent")
    def handle_holonym(self, message):
        query = message.data["query"]
        lang = self.lang.split("-")[0]
        items = self._word_data(query, lang).get("holonyms") or []
        if items:
            self.speak(random.choice(items))
        else:
            self.speak_dialog("no_answer")

    @intent_handler("hyponym.intent")
    def handle_hyponym(self, message):
        query = message.data["query"]
        lang = self.lang.split("-")[0]
        items = self._word_data(query, lang).get("hyponyms") or []
        if items:
            self.speak(random.choice(items))
        else:
            self.speak_dialog("no_answer")

    @intent_handler("hypernym.intent")
    def handle_hypernym(self, message):
        query = message.data["query"]
        lang = self.lang.split("-")[0]
        items = self._word_data(query, lang).get("hypernyms") or []
        if items:
            self.speak(random.choice(items))
        else:
            self.speak_dialog("no_answer")
