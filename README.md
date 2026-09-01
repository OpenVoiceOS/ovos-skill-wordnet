# ovos-skill-wordnet

[![PyPI](https://img.shields.io/pypi/v/ovos-skill-wordnet)](https://pypi.org/project/ovos-skill-wordnet/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)

WordNet skill for [OpenVoiceOS](https://openvoiceos.org). It adds a voice interface on top of [ovos-wordnet-plugin](https://github.com/OpenVoiceOS/ovos-wordnet-plugin), which handles all WordNet lookups, intent detection, and translation.

The skill supports three answer modes:

- **Explicit intent** handles utterances that name WordNet directly (for example, "ask wordnet about dog"). These always go to this skill. The plugin's built-in intent parser detects the relation type (definition, antonym, hypernym, and more) and returns a spoken-language response.
- **Common Query** handles dictionary-style questions through the [OVOS Common Query pipeline](https://github.com/OpenVoiceOS/ovos-common-query-pipeline-plugin). It competes with other knowledge skills and returns confidence 0.6 for definition matches.
- **Fallback** catches utterances that no other skill answers. The fallback handler intercepts utterances that match `WordnetQuery.voc` (dictionary and thesaurus keywords) and queries the plugin for an answer before OVOS says "I don't know".

---

## Installation

```bash
pip install ovos-skill-wordnet
```

No API key is required. WordNet data downloads automatically on first use (about 30-60 MB for English) and stays cached locally. When no native gloss is available, the system translation plugin translates non-English definitions.

---

## Answer modes

### Explicit intent

These always route to this skill because they name WordNet explicitly:

- "Ask wordnet about dog"
- "Search word net for happy"
- "What does wordnet say about bank?"

The plugin detects which relation was asked (definition, antonym, hypernym, hyponym, holonym, lemma) and returns a natural-language response.

### Common Query pipeline

When the [Common Query pipeline plugin](https://github.com/OpenVoiceOS/ovos-common-query-pipeline-plugin) is active, this skill competes against other knowledge skills (for example, Wolfram Alpha or Wikipedia). Any bare definition query can win:

- "What is a dog?"
- "What does melancholy mean?"

### Fallback

The fallback handler registers at priority 90. It only intercepts utterances that contain dictionary or thesaurus keywords (`definition`, `antonym`, `synonym`, `meaning`, `opposite`, `hypernym`, `hyponym`, and more). All other utterances pass through immediately, so unrelated fallbacks stay unaffected.

---

## Supported languages

The skill supports 31 languages. Definitions are native for **English** (Open English WordNet 2024) and **German** (ODENet). All other languages use OMW 1.4 lemmas. Where a native definition is unavailable, the configured OVOS translation plugin translates the English definition.

| BCP-47 | Language |
|--------|----------|
| `ar` | Arabic |
| `bg` | Bulgarian |
| `ca` | Catalan |
| `cmn` | Mandarin Chinese |
| `da` | Danish |
| `de` | German |
| `el` | Greek |
| `en` | English |
| `es` | Spanish |
| `eu` | Basque |
| `fi` | Finnish |
| `fr` | French |
| `gl` | Galician |
| `he` | Hebrew |
| `hr` | Croatian |
| `id` | Indonesian |
| `is` | Icelandic |
| `it` | Italian |
| `ja` | Japanese |
| `lt` | Lithuanian |
| `nb` | Norwegian Bokmål |
| `nl` | Dutch |
| `nn` | Norwegian Nynorsk |
| `pl` | Polish |
| `pt` | Portuguese |
| `ro` | Romanian |
| `sk` | Slovak |
| `sl` | Slovenian |
| `sv` | Swedish |
| `th` | Thai |
| `zsm` | Standard Malay |

---

## Related projects

- [OpenVoiceOS/ovos-wordnet-plugin](https://github.com/OpenVoiceOS/ovos-wordnet-plugin) does the WordNet lookups, intent detection, and translation that this skill exposes as a voice interface.
- [OpenVoiceOS/ovos-common-query-pipeline-plugin](https://github.com/OpenVoiceOS/ovos-common-query-pipeline-plugin) routes dictionary-style questions to this skill and other knowledge skills.

---

## License

Apache 2.0. See [LICENSE](LICENSE).
