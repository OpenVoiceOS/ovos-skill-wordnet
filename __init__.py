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
from typing import Optional, Dict, Tuple, Any

import nltk
from nltk.corpus import wordnet as wn
from nltk.data import find

from ovos_plugin_manager.templates.language import LanguageTranslator, LanguageDetector
from ovos_plugin_manager.templates.solvers import QuestionSolver
from ovos_utils.lang import standardize_lang_tag
from ovos_workshop.decorators import intent_handler, common_query
from ovos_workshop.skills.ovos import OVOSSkill


def download_nltk_resource(res: str, res_type: str = "taggers"):
    """
    Download necessary NLTK resource if not already downloaded.
    """

    resource_name = f'{res_type}/{res}.zip'
    try:
        find(resource_name)
    except LookupError:
        # Download resource if not already present
        nltk.download(res)


class Wordnet:
    LANGMAP = {'en': 'eng', 'als': 'als', 'arb': 'arb', 'bg': 'bul', 'cmn': 'cmn',
               'da': 'dan', 'el': 'ell', 'fi': 'fin', 'fr': 'fra', 'he': 'heb',
               'hr': 'hrv', 'is': 'isl', 'it': 'ita', 'it-iwn': 'ita_iwn', 'ja': 'jpn',
               'ca': 'cat', 'eu': 'eus', 'gl': 'glg', 'es': 'spa', 'id': 'ind', 'zsm': 'zsm',
               'nl': 'nld', 'nn': 'nno', 'nb': 'nob', 'pl': 'pol', 'pt': 'por', 'ro': 'ron',
               'lt': 'lit', 'sk': 'slk', 'sl': 'slv', 'sv': 'swe', 'th': 'tha'}
    translator: Optional[LanguageTranslator] = None
    download_nltk_resource("wordnet", "corpora")
    download_nltk_resource("omw-1.4", "corpora")

    @staticmethod
    def get_synsets(word, pos=wn.NOUN, lang: Optional[str] = "en"):
        lang = Wordnet.LANGMAP[standardize_lang_tag(lang.split("-")[0])]
        synsets = wn.synsets(word, pos=pos, lang=lang)
        if not len(synsets):
            return []
        return synsets

    @staticmethod
    def get_definition(word, pos=wn.NOUN, synset=None, lang: Optional[str] = "en"):
        lang = Wordnet.LANGMAP[standardize_lang_tag(lang.split("-")[0])]
        if synset is None:
            synsets = wn.synsets(word, pos=pos, lang=lang)
            if not len(synsets):
                return []
            synset = synsets[0]
        defi = synset.definition(lang=lang)
        if not defi:
            # translate if possible
            if Wordnet.translator is not None:
                return Wordnet.translator.translate(text=synset.definition(lang="eng"),
                                                    target=standardize_lang_tag(lang),
                                                    source="en")
        return defi

    @staticmethod
    def get_examples(word, pos=wn.NOUN, synset=None, lang: Optional[str] = "en"):
        lang = Wordnet.LANGMAP[standardize_lang_tag(lang.split("-")[0])]
        if synset is None:
            synsets = wn.synsets(word, pos=pos, lang=lang)
            if not len(synsets):
                return []
            synset = synsets[0]
        return synset.examples(lang=lang)

    @staticmethod
    def get_lemmas(word, pos=wn.NOUN, synset=None, lang: Optional[str] = "en"):
        lang = Wordnet.LANGMAP[standardize_lang_tag(lang.split("-")[0])]
        if synset is None:
            synsets = wn.synsets(word, pos=pos, lang=lang)
            if not len(synsets):
                return []
            synset = synsets[0]
        return [l.name().replace("_", " ") for l in synset.lemmas(lang=lang)]

    @staticmethod
    def get_hypernyms(word, pos=wn.NOUN, synset=None, lang: Optional[str] = "en"):
        lang = Wordnet.LANGMAP[standardize_lang_tag(lang.split("-")[0])]
        if synset is None:
            synsets = wn.synsets(word, pos=pos, lang=lang)
            if not len(synsets):
                return []
            synset = synsets[0]

        # Translate hypernyms to lang
        lang_h = []
        for hypernym in synset.hypernyms():
            lang_h += [lemma.name().split(".")[0].replace("_", " ")
                       for lemma in hypernym.lemmas(lang=lang)]
        return lang_h

    @staticmethod
    def get_hyponyms(word, pos=wn.NOUN, synset=None, lang: Optional[str] = "en"):
        lang = Wordnet.LANGMAP[standardize_lang_tag(lang.split("-")[0])]
        if synset is None:
            synsets = wn.synsets(word, pos=pos, lang=lang)
            if not len(synsets):
                return []
            synset = synsets[0]
        # Translate hyponyms to lang
        lang_h = []
        for hyponym in synset.hyponyms():
            lang_h += [lemma.name().split(".")[0].replace("_", " ")
                       for lemma in hyponym.lemmas(lang=lang)]
        return lang_h

    @staticmethod
    def get_holonyms(word, pos=wn.NOUN, synset=None, lang: Optional[str] = "en"):
        lang = Wordnet.LANGMAP[standardize_lang_tag(lang.split("-")[0])]
        if synset is None:
            synsets = wn.synsets(word, pos=pos, lang=lang)
            if not len(synsets):
                return []
            synset = synsets[0]
        # Translate holonyms to lang
        lang_h = []
        for holonym in synset.member_holonyms():
            lang_h += [lemma.name().split(".")[0].replace("_", " ")
                       for lemma in holonym.lemmas(lang=lang)]
        return lang_h

    @staticmethod
    def get_root_hypernyms(word, pos=wn.NOUN, synset=None, lang: Optional[str] = "en"):
        lang = Wordnet.LANGMAP[standardize_lang_tag(lang.split("-")[0])]
        if synset is None:
            synsets = wn.synsets(word, pos=pos, lang=lang)
            if not len(synsets):
                return []
            synset = synsets[0]
        # Translate hypernyms to lang
        lang_h = []
        for hypernym in synset.root_hypernyms():
            lang_h += [lemma.name().split(".")[0].replace("_", " ")
                       for lemma in hypernym.lemmas(lang=lang)]
        return lang_h

    @staticmethod
    def common_hypernyms(word, word2, pos=wn.NOUN, lang: Optional[str] = "en"):
        lang = Wordnet.LANGMAP[standardize_lang_tag(lang.split("-")[0])]
        synsets = wn.synsets(word, pos=pos, lang=lang)
        if not len(synsets):
            return []
        synset = synsets[0]
        synsets = wn.synsets(word2, pos=pos, lang=lang)
        if not len(synsets):
            return []
        synset2 = synsets[0]
        return [l.name().split(".")[0].replace("_", " ") for l in
                synset.lowest_common_hypernyms(synset2, lang=lang)]

    @staticmethod
    def get_antonyms(word, pos=wn.NOUN, synset=None, lang: Optional[str] = "en"):
        lang = Wordnet.LANGMAP[standardize_lang_tag(lang.split("-")[0])]
        if synset is None:
            synsets = wn.synsets(word, pos=pos, lang=lang)
            if not len(synsets):
                return []
            synset = synsets[0]
        lemmas = synset.lemmas(lang=lang)
        if not len(lemmas):
            return []
        lemma = lemmas[0]
        antonyms = lemma.antonyms()

        return [l.name().split(".")[0].replace("_", " ") for l in antonyms]

    @classmethod
    def query(cls, query, pos=wn.NOUN, synset=None, lang: Optional[str] = "en"):
        lang = Wordnet.LANGMAP[standardize_lang_tag(lang.split("-")[0])]
        if synset is None:
            synsets = wn.synsets(query, pos=pos, lang=lang)
            if not len(synsets):
                return {}
            synset = synsets[0]
        res = {"lemmas": cls.get_lemmas(query, pos=pos, synset=synset, lang=lang),
               "antonyms": cls.get_antonyms(query, pos=pos, synset=synset, lang=lang),
               "holonyms": cls.get_holonyms(query, pos=pos, synset=synset, lang=lang),
               "hyponyms": cls.get_hyponyms(query, pos=pos, synset=synset, lang=lang),
               "hypernyms": cls.get_hypernyms(query, pos=pos, synset=synset, lang=lang),
               "root_hypernyms": cls.get_root_hypernyms(query, pos=pos, synset=synset, lang=lang),
               "definition": cls.get_definition(query, pos=pos, synset=synset, lang=lang)}
        return res


class WordnetSkill(OVOSSkill):

    def initialize(self):
        self.solver = WordnetSolver(translator=self.translator,
                                    detector=self.lang_detector)

    @common_query()
    def match_common_query(self, phrase: str, lang: str) -> Tuple[Optional[str], float]:
        res = self.solver.get_data(phrase, lang=lang).get("definition")
        if res:
            return res, 0.6
        return None, 0.0

    # intents
    @intent_handler("search_wordnet.intent")
    def handle_search(self, message):
        self.handle_definition(message)

    @intent_handler("definition.intent")
    def handle_definition(self, message):
        query = message.data["query"]
        res = self.solver.get_data(query, lang=self.lang).get("definition")
        if res:
            self.speak(res)
        else:
            self.speak_dialog("no_answer")

    # TODO - plural vs singular questions
    # TODO - "N lemmas of {query}"
    @intent_handler("lemma.intent")
    def handle_lemma(self, message):
        query = message.data["query"]
        res = self.solver.get_data(query, lang=self.lang).get("lemmas")
        if res:
            self.speak(random.choice(res))
        else:
            self.speak_dialog("no_answer")

    @intent_handler("antonym.intent")
    def handle_antonym(self, message):
        query = message.data["query"]
        res = self.solver.get_data(query, lang=self.lang).get("antonyms")
        if res:
            self.speak(random.choice(res))
        else:
            self.speak_dialog("no_answer")

    @intent_handler("holonym.intent")
    def handle_holonym(self, message):
        query = message.data["query"]
        res = self.solver.get_data(query, lang=self.lang).get("holonyms")
        if res:
            self.speak(random.choice(res))
        else:
            self.speak_dialog("no_answer")

    @intent_handler("hyponym.intent")
    def handle_hyponym(self, message):
        query = message.data["query"]
        res = self.solver.get_data(query, lang=self.lang).get("hyponyms")
        if res:
            self.speak(random.choice(res))
        else:
            self.speak_dialog("no_answer")

    @intent_handler("hypernym.intent")
    def handle_hypernym(self, message):
        query = message.data["query"]
        res = self.solver.get_data(query, lang=self.lang).get("hypernyms")
        if res:
            self.speak(random.choice(res))
        else:
            self.speak_dialog("no_answer")


class WordnetSolver(QuestionSolver):
    """
    A solver for answering questions using Wordnet
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 translator: Optional[LanguageTranslator] = None,
                 detector: Optional[LanguageDetector] = None):
        super().__init__(config, enable_tx=False, priority=70,
                         translator=translator, detector=detector)
        Wordnet.translator = self._translator

    def get_data(self, query: str, lang: Optional[str] = "en",
                 units: Optional[str] = None, pos="auto") -> Dict[str, str]:
        """
        Retrieves WordNet data for the given query.

        Args:
            query (str): The query string.
            lang (Optional[str]): The language of the query. Defaults to None.
            units (Optional[str]): Optional units for the query. Defaults to None.

        Returns:
            Dict[str, str]: A dictionary containing WordNet data such as lemmas, antonyms, definitions, etc.
        """
        p = wn.NOUN if pos not in [wn.NOUN, wn.ADJ, wn.VERB] else pos

        lang = Wordnet.LANGMAP[standardize_lang_tag(lang.split("-")[0])]
        synsets = wn.synsets(query, pos=p, lang=lang)
        if not synsets and pos == "auto" and p == wn.NOUN:
            # try looking for an adjective
            p = wn.ADJ
            synsets = wn.synsets(query, pos=p, lang=lang)
        if not synsets and pos == "auto" and p == wn.ADJ:
            # try looking for a verb
            p = wn.VERB
            synsets = wn.synsets(query, pos=p, lang=lang)

        if not synsets:
            return {}

        synset = synsets[0]
        res = {
            "postag": "ADJ" if p == wn.ADJ else "VERB" if p == wn.VERB else "NOUN",
            "lemmas": Wordnet.get_lemmas(query, pos=pos, synset=synset, lang=lang),
            "antonyms": Wordnet.get_antonyms(query, pos=pos, synset=synset, lang=lang),
            "holonyms": Wordnet.get_holonyms(query, pos=pos, synset=synset, lang=lang),
            "hyponyms": Wordnet.get_hyponyms(query, pos=pos, synset=synset, lang=lang),
            "hypernyms": Wordnet.get_hypernyms(query, pos=pos, synset=synset, lang=lang),
            "root_hypernyms": Wordnet.get_root_hypernyms(query, pos=pos, synset=synset, lang=lang),
            "definition": Wordnet.get_definition(query, pos=pos, synset=synset, lang=lang)
        }
        return res

    def get_spoken_answer(self, query: str,
                          lang: Optional[str] = None,
                          units: Optional[str] = None) -> Optional[str]:
        """
        Obtain the spoken answer for a given query.

        Args:
            query (str): The query text.
            lang (Optional[str]): Optional language code. Defaults to None.
            units (Optional[str]): Optional units for the query. Defaults to None.

        Returns:
            str: The spoken answer as a text response.
        """
        data = self.get_data(query, lang=lang)
        return data.get("definition")


WORDNET_PERSONA = {
  "name": "Wordnet",
  "solvers": [
    "ovos-solver-wordnet-plugin",
    "ovos-solver-failure-plugin"
  ]
}

if __name__ == "__main__":
    print(list(Wordnet.LANGMAP))

    d = WordnetSolver()

    query = "what is the definition of computer"

    ans = d.get_data("computador", lang="pt")
    print("pt", ans)
    # {'postag': 'NOUN',
    # 'lemmas': ['Calculadoras', 'calculador', 'calculadora', 'calculista', 'computador'],
    # 'antonyms': [],
    # 'holonyms': [],
    # 'hyponyms': ['quipo', 'máquina de somar', 'Ossos de Napier', 'Ossos de napier', 'Abaco', 'ábaco'],
    # 'hypernyms': ['maquinaria', 'máquina'],
    # 'root_hypernyms': ['ente', 'entidade', 'ser'],
    # 'definition': "Uma máquina pequena utilizada para cálculos matemáticos"}

    # full answer
    ans = d.get_data("computer")["definition"]
    print("en", ans)
    # a machine for performing calculations automatically
