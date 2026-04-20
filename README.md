# ovos-skill-wordnet

[![PyPI](https://img.shields.io/pypi/v/ovos-skill-wordnet)](https://pypi.org/project/ovos-skill-wordnet/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)

WordNet skill for [OpenVoiceOS](https://openvoiceos.org). Adds a voice interface on top of [ovos-wordnet-plugin](https://github.com/OpenVoiceOS/ovos-wordnet-plugin), which handles all WordNet lookups, intent detection, and translation.

Supports two answer modes:

- **Explicit intent** — handles utterances that target WordNet directly (e.g. "ask wordnet about dog"). These always go to this skill. The plugin's built-in intent parser detects the relation type (definition, antonym, hypernym, …) and returns a spoken-language response.
- **Common Query** — handles dictionary-style questions (e.g. "what is a dog?") via the [OVOS Common Query pipeline](https://github.com/OpenVoiceOS/ovos-common-query-pipeline-plugin). The pipeline asks all registered knowledge skills and picks the best answer.

---

## Installation

```bash
pip install ovos-skill-wordnet
```

No API key required. WordNet data is downloaded automatically on first use and cached locally.

---

## Explicit intent utterances

These always route to this skill because they name WordNet explicitly:

- "Ask wordnet about dog"
- "Search word net for happy"
- "What does wordnet say about bank?"

The plugin then detects which relation was asked and responds accordingly. You can also ask relation questions directly without naming WordNet — those are handled by the Common Query pipeline.

## Common Query utterances

These go through the pipeline — WordNet answers if it wins:

- "What is the definition of bank?"
- "What are the antonyms of happy?"
- "What are the hypernyms of dog?"
- "What is a lemma of run?"

---

## Common Query pipeline

When the [Common Query pipeline plugin](https://github.com/OpenVoiceOS/ovos-common-query-pipeline-plugin) is active, this skill competes against other knowledge skills (e.g. Wolfram Alpha, Wikipedia) to answer dictionary and thesaurus questions. WordNet returns a confidence of 0.6 for definition matches.

---

## Supported languages

Definitions are native for English (Open English WordNet 2024) and German (ODENet). All other languages use OMW 1.4 lemmas; where native definitions are unavailable the English definition is machine-translated via the system translation plugin.

See [ovos-wordnet-plugin](https://github.com/OpenVoiceOS/ovos-wordnet-plugin) for the full language list.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
