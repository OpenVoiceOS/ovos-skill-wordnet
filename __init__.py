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
#
import random

from ovos_classifiers.opm.nltk import WordnetSolverPlugin
from ovos_workshop.decorators import intent_handler
from ovos_workshop.skills.common_query_skill import CommonQuerySkill, CQSMatchLevel


class WordnetSkill(CommonQuerySkill):
    def initialize(self):
        self.wordnet = WordnetSolverPlugin()

    # intents
    @intent_handler("search_wordnet.intent")
    def handle_search(self, message):
        query = message.data["query"]
        summary = self.wordnet.spoken_answer(query, lang=self.lang)
        if summary:
            self.speak(summary)
        else:
            self.speak_dialog("no_answer")

    @intent_handler("definition.intent")
    def handle_definition(self, message):
        query = message.data["query"]
        res = self.wordnet.search(query, lang=self.lang).get("definition")
        if res:
            self.speak(res)
        else:
            self.speak_dialog("no_answer")

    # TODO - plural vs singular questions
    # TODO - "N lemmas of {query}"
    @intent_handler("lemma.intent")
    def handle_lemma(self, message):
        query = message.data["query"]
        res = self.wordnet.search(query, lang=self.lang).get("lemmas")
        if res:
            self.speak(random.choice(res))
        else:
            self.speak_dialog("no_answer")

    @intent_handler("antonym.intent")
    def handle_antonym(self, message):
        query = message.data["query"]
        res = self.wordnet.search(query, lang=self.lang).get("antonyms")
        if res:
            self.speak(random.choice(res))
        else:
            self.speak_dialog("no_answer")

    @intent_handler("holonym.intent")
    def handle_holonym(self, message):
        query = message.data["query"]
        res = self.wordnet.search(query, lang=self.lang).get("holonyms")
        if res:
            self.speak(random.choice(res))
        else:
            self.speak_dialog("no_answer")

    @intent_handler("hyponym.intent")
    def handle_hyponym(self, message):
        query = message.data["query"]
        res = self.wordnet.search(query, lang=self.lang).get("hyponyms")
        if res:
            self.speak(random.choice(res))
        else:
            self.speak_dialog("no_answer")

    @intent_handler("hypernym.intent")
    def handle_hypernym(self, message):
        query = message.data["query"]
        res = self.wordnet.search(query, lang=self.lang).get("hypernyms")
        if res:
            self.speak(random.choice(res))
        else:
            self.speak_dialog("no_answer")

    # common query
    def CQS_match_query_phrase(self, phrase):
        summary = self.wordnet.spoken_answer(query, lang=self.lang)
        if summary:
            self.log.info(f"Wordnet answer: {summary}")
            return (phrase, CQSMatchLevel.CATEGORY, summary,
                    {'query': phrase,
                     'answer': summary})

    def CQS_action(self, phrase, data):
        pass


if __name__ == "__main__":
    from ovos_utils.fakebus import FakeBus

    d = WordnetSkill(skill_id="wordnet.ovos", bus=FakeBus())

    query = "what is the definition of computer"

    ans = d.wordnet.search("computer", context={"lang": "es-es"})
    print(ans)
    # {'lemmas': ['computer', 'computing machine', 'computing device', 'data processor', 'electronic computer', 'information processing system'],
    # 'antonyms': [],
    # 'holonyms': [],
    # 'hyponyms': ['analog computer', 'digital computer', 'home computer', 'node', 'number cruncher', 'pari-mutuel machine', 'predictor', 'server', 'turing machine', 'web site'],
    # 'hypernyms': ['machine'],
    # 'root_hypernyms': ['entity'],
    # 'definition': 'a machine for performing calculations automatically'}

    # full answer
    ans = d.wordnet.spoken_answer(query)
    print(ans)
    # a machine for performing calculations automatically

    # bidirectional auto translate by passing lang
    sentence = d.wordnet.spoken_answer("qual é a definição de computador", lang="pt-pt")
    print(sentence)
    # uma máquina para realizar cálculos automaticamente
