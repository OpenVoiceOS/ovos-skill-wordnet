# ovos-skill-wordnet

[![PyPI](https://img.shields.io/pypi/v/ovos-skill-wordnet)](https://pypi.org/project/ovos-skill-wordnet/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)

WordNet skill for [OpenVoiceOS](https://openvoiceos.org). Adds a voice interface on top of [ovos-wordnet-plugin](https://github.com/OpenVoiceOS/ovos-wordnet-plugin), which handles all WordNet lookups, intent detection, and translation.

Supports three answer modes:

- **Explicit intent** — handles utterances that target WordNet directly (e.g. "ask wordnet about dog"). These always go to this skill. The plugin's built-in intent parser detects the relation type (definition, antonym, hypernym, …) and returns a spoken-language response.
- **Common Query** — handles dictionary-style questions via the [OVOS Common Query pipeline](https://github.com/OpenVoiceOS/ovos-common-query-pipeline-plugin). Competes with other knowledge skills; returns confidence 0.6 for definition matches.
- **Fallback** — if no other skill answers, the fallback handler intercepts utterances that match `WordnetQuery.voc` (dictionary/thesaurus keywords) and queries the plugin for an answer before OVOS says "I don't know".

---

## Installation

```bash
pip install ovos-skill-wordnet
```

No API key required. WordNet data is downloaded automatically on first use (~30–60 MB for English) and cached locally. Non-English definitions are translated via the system translation plugin where no native gloss is available.

---

## Answer modes

### Explicit intent

These always route to this skill because they name WordNet explicitly:

- "Ask wordnet about dog"
- "Search word net for happy"
- "What does wordnet say about bank?"

The plugin detects which relation was asked (definition, antonym, hypernym, hyponym, holonym, lemma) and returns a natural-language response.

### Common Query pipeline

When the [Common Query pipeline plugin](https://github.com/OpenVoiceOS/ovos-common-query-pipeline-plugin) is active, this skill competes against other knowledge skills (e.g. Wolfram Alpha, Wikipedia). Any bare definition query can win:

- "What is a dog?"
- "What does melancholy mean?"

### Fallback

Registered at priority 90. Only intercepts utterances containing dictionary/thesaurus keywords (`definition`, `antonym`, `synonym`, `meaning`, `opposite`, `hypernym`, `hyponym`, …). All other utterances pass through immediately so unrelated fallbacks are not affected.

---

## Supported languages

31 languages are supported. Definitions are native for **English** (Open English WordNet 2024) and **German** (ODENet). All other languages use OMW 1.4 lemmas; where native definitions are unavailable the English definition is translated via the configured OVOS translation plugin.

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

## License

Apache 2.0 — see [LICENSE](LICENSE).
