"""Context-aware synonym generation backed by a local LLM served by Ollama.

WordNet was the wrong tool for this job. It ranks by lemma frequency across the
whole corpus, which means it happily returns a noun for a verb ("released" ->
"issue"), a different sense entirely ("can" -> "fire", "pot", "ass"), or an
archaic/register-mismatched word. Every one of those breaks the sentence it is
substituted into, because the substitution is mechanical: whatever comes back is
swapped into running prose.

A small instruction-tuned model fixes this because it sees the actual sentence.
Asked "which words in this document can be swapped for a natural alternative
without changing the meaning or breaking the grammar", it answers in context
instead of by corpus frequency.

Design constraints, in order of importance:

1. **Nothing is trusted.** The model's output is validated against the source
   document before it is used: every original must actually appear in the prose,
   every alternative must be a plain word, and no alternative may collide with
   another group's original (which would allow chained, compounding rewrites).
2. **Failure is loud but not fatal.** A missing model or a stopped container must
   not abort a multi-variant generation run; the caller gets an actionable error
   and can continue without synonyms.
3. **One call per document.** The map is generated once and applied to every
   variant, so latency is paid once, not per variant.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request

#: Ollama's default local endpoint. Overridable for a remote or containerised
#: daemon; a bare ``host:port`` is also accepted and gets an http:// scheme.
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"

#: Small enough to run on CPU with a 2 GB GPU in the box. Instruction-tuned and
#: multilingual, which matters because the map is generated per document language.
DEFAULT_MODEL = "qwen2.5:3b"

#: Alternatives kept per word, excluding the original. Three is enough to make
#: variants diverge (4^N combinations) without diluting quality.
MAX_SYNONYMS = 3

#: Upper bound on groups per document. A long document otherwise produces a map
#: so dense that nearly every sentence is rewritten and the variant drifts away
#: from the original's message.
MAX_GROUPS = 60

#: Generation is near-deterministic on purpose: the *variants* provide the
#: randomness, via random selection from each group. Jittering the vocabulary
#: itself would make output irreproducible without adding usefulness.
TEMPERATURE = 0.2

_REQUEST_TIMEOUT = 180

#: The instruction prompt. Constraints are stated as rules, then again as a
#: worked example, because small models follow examples far more reliably than
#: prose rules. Short phrases are explicitly allowed: they are what small models
#: produce well, and swapping a phrase keeps its collocation intact.
_PROMPT_TEMPLATE = """You rewrite a document into a variant with different wording.

Find spans of text that can each be swapped for a natural alternative WITHOUT
changing meaning, tone or grammar. A span may be a single word OR a short phrase
of up to three words ("security update" -> "security patch").

RULES
- Every "original" must appear verbatim in the document, lowercase, with no
  surrounding punctuation.
- Each alternative must fit the exact same slot: same part of speech, same tense,
  same number, same person. ("released" -> "published", never "release".)
- Keep meaning, register and any factual or legal claim identical. When unsure,
  leave the span out.
- NEVER pick: proper nouns, brand or product names, personal names, URLs, email
  addresses, acronyms, numbers, or the label of a button/link.
- Alternatives must be common, everyday vocabulary - no archaic or obscure terms.
- Give at most {max_synonyms} alternatives per span, and skip a span that has no
  safe alternative.
- Be thorough: aim for {target_groups} spans, and never exceed {max_groups}.
- Write every alternative in {language}.

WORKED EXAMPLE
Document: "The report was published yesterday. The team confirmed the total."
Answer: {{"groups": [
  {{"original": "published", "synonyms": ["released", "issued"]}},
  {{"original": "confirmed", "synonyms": ["verified"]}},
  {{"original": "total", "synonyms": ["sum", "amount"]}}
]}}

Return ONLY that JSON object, with no commentary and no markdown fence.

DOCUMENT:
\"\"\"
{document}
\"\"\"
"""


class SynonymDataUnavailable(RuntimeError):
    """Raised when the local LLM backing synonym generation cannot be used.

    Kept under this name because callers already handle it; it now reports a
    transport/model problem rather than a missing corpus.
    """


#: ISO 639-1 -> English language name, so the prompt can name the target language
#: in words. Unknown codes fall back to the code itself, which the model still
#: understands.
_LANGUAGE_NAMES = {
    "ar": "Arabic", "bg": "Bulgarian", "ca": "Catalan", "cs": "Czech",
    "da": "Danish", "de": "German", "el": "Greek", "en": "English",
    "es": "Spanish", "eu": "Basque", "fa": "Persian", "fi": "Finnish",
    "fr": "French", "he": "Hebrew", "hr": "Croatian", "hu": "Hungarian",
    "id": "Indonesian", "is": "Icelandic", "it": "Italian", "ja": "Japanese",
    "ko": "Korean", "lt": "Lithuanian", "ms": "Malay", "nl": "Dutch",
    "no": "Norwegian", "pl": "Polish", "pt": "Portuguese", "ro": "Romanian",
    "ru": "Russian", "sk": "Slovak", "sl": "Slovenian", "sv": "Swedish",
    "th": "Thai", "tr": "Turkish", "uk": "Ukrainian", "vi": "Vietnamese",
    "zh": "Chinese",
}

#: In-process cache keyed by (model, text digest). One document is normally
#: processed once, but repeated runs over the same input are common and a 3B
#: model on CPU is not free.
_CACHE: dict[tuple[str, str], list[list[str]]] = {}


def _ollama_host(explicit: str | None = None) -> str:
    host = (explicit or "").strip() or os.environ.get("OLLAMA_HOST", "").strip() or DEFAULT_OLLAMA_HOST
    if "://" not in host:
        host = f"http://{host}"
    return host.rstrip("/")


def _model(explicit: str | None = None) -> str:
    return (explicit or "").strip() or os.environ.get("OLLAMA_MODEL", "").strip() or DEFAULT_MODEL


def _language_name(lang: str) -> str:
    code = lang.strip().lower().replace("_", "-").split("-")[0]
    return _LANGUAGE_NAMES.get(code, code or "English")


def _normalize_word(token: str) -> str:
    token = token.strip().lower()
    token = re.sub(r"[_\-]+", " ", token)
    return re.sub(r"\s+", " ", token)


def _post_json(
    path: str,
    payload: dict,
    *,
    host: str | None = None,
    model: str | None = None,
    timeout: int = _REQUEST_TIMEOUT,
) -> dict:
    base = _ollama_host(host)
    url = f"{base}{path}"
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace").strip()
        except Exception:  # pragma: no cover - body already unusable
            pass
        if exc.code == 404:
            wanted = _model(model)
            raise SynonymDataUnavailable(
                f"The model '{wanted}' is not available in Ollama. "
                f"Pull it with: ollama pull {wanted}\n"
                f"(or set OLLAMA_MODEL to a model you already have)"
            ) from exc
        raise SynonymDataUnavailable(
            f"Ollama rejected the request ({exc.code}): {detail or exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise SynonymDataUnavailable(
            f"Could not reach Ollama at {base} ({exc.reason}).\n"
            "Start it with: docker compose up -d ollama\n"
            "Or install it locally, then run: ollama serve"
        ) from exc
    except (TimeoutError, json.JSONDecodeError) as exc:
        raise SynonymDataUnavailable(
            f"Ollama at {base} did not return usable JSON within "
            f"{timeout}s. A smaller OLLAMA_MODEL is faster; try qwen2.5:1.5b."
        ) from exc


def check_available(model: str | None = None, host: str | None = None) -> None:
    """Raise :class:`SynonymDataUnavailable` unless the model can be reached.

    Called before a long generation run so the user learns about a missing model
    immediately instead of after the first document.
    """
    base = _ollama_host(host)
    url = f"{base}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SynonymDataUnavailable(
            f"Could not reach Ollama at {base} ({exc.reason}).\n"
            "Start it with: docker compose up -d ollama"
        ) from exc
    except (TimeoutError, json.JSONDecodeError) as exc:
        raise SynonymDataUnavailable(
            f"Ollama at {base} did not answer the model-list request."
        ) from exc

    installed = {
        str(entry.get("name", "")).split(":")[0]
        for entry in payload.get("models", [])
        if isinstance(entry, dict)
    }
    wanted = _model(model)
    if wanted.split(":")[0] not in installed:
        raise SynonymDataUnavailable(
            f"The model '{wanted}' is not installed in Ollama.\n"
            f"Pull it with: docker compose run --rm ollama-pull\n"
            f"or: ollama pull {wanted}"
        )


def _normalize_phrase(text: str) -> str:
    """Normalize a word or short phrase for use as a map key.

    Phrases are legitimate here: the substitution engine matches on word
    boundaries, so a group like ``security update | security patch`` replaces the
    whole phrase atomically. That is *safer* than swapping single words, because
    it keeps collocations intact, and it is what small models produce reliably.
    """
    token = text.strip().lower()
    token = re.sub(r"\s+", " ", token)
    return token.strip(" .,;:!?\"'()[]")


def _contains(haystack: str, needle: str) -> bool:
    """True when ``needle`` appears inside ``haystack`` on word boundaries."""
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None


def _parse_groups(raw: str, prose: str, *, max_groups: int) -> list[list[str]]:
    """Turn the model's JSON into validated ``[original, alt, ...]`` groups.

    Validation is deliberately strict: a single bad group can rewrite a legal
    claim or break a sentence in every variant, and the model has no way to know
    it was wrong.

    Single words and short phrases are both accepted. Phrases are matched by the
    same word-boundary regex as single words, so ``security update`` -> ``security
    patch`` is applied atomically.
    """
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []

    # Accept the documented shape plus the near-misses models actually emit.
    entries = payload.get("groups") if isinstance(payload, dict) else payload
    if isinstance(entries, dict):
        entries = entries.get("groups")
    if not isinstance(entries, list):
        return []

    # Punctuation is stripped so "released," still matches "released".
    prose_tokens = set(re.findall(r"[^\W\d_]+", prose.lower(), re.UNICODE))
    prose_normalized = _normalize_phrase(prose)

    def appears_in_prose(phrase: str) -> bool:
        if " " in phrase:
            return re.search(
                rf"(?<!\w){re.escape(phrase)}(?!\w)", prose_normalized
            ) is not None
        return phrase in prose_tokens

    candidates: list[tuple[str, list[str]]] = []
    seen_originals: set[str] = set()

    for entry in entries:
        if isinstance(entry, dict):
            original = entry.get("original", entry.get("word", ""))
            synonyms = entry.get("synonyms", entry.get("alternatives", []))
        elif isinstance(entry, (list, tuple)) and entry:
            original, synonyms = entry[0], list(entry[1:])
        else:
            continue

        original = _normalize_phrase(str(original))
        if not original or len(original.split()) > 3 or original in seen_originals:
            continue
        # The phrase must genuinely occur, otherwise the pattern can never match.
        if not appears_in_prose(original):
            continue

        cleaned: list[str] = []
        for candidate in synonyms if isinstance(synonyms, list) else []:
            phrase = _normalize_phrase(str(candidate))
            if not phrase or len(phrase.split()) > 3:
                continue
            # Only letters, spaces and apostrophes are safe inside the regex
            # alternation and inside running prose.
            if not re.fullmatch(r"[^\W\d_]+(?: [^\W\d_]+)*", phrase, re.UNICODE):
                continue
            if len(phrase) < 3 or phrase == original or phrase in cleaned:
                continue
            cleaned.append(phrase)
            if len(cleaned) >= MAX_SYNONYMS:
                break

        if not cleaned:
            continue

        seen_originals.add(original)
        candidates.append((original, cleaned))

    # Longer spans carry more context, so they are the safer swap and win when two
    # candidates overlap. Sorting longest-first also makes the overlap test below
    # deterministic instead of dependent on the model's ordering.
    candidates.sort(key=lambda item: (-len(item[0].split()), -len(item[0])))

    chosen: list[tuple[str, list[str]]] = []
    for original, synonyms in candidates:
        # A span nested inside an already-chosen longer span would either never
        # match (the longer rule rewrites it first) or, depending on rule order,
        # replace part of the longer span and produce a hybrid no one wrote.
        if any(
            _contains(existing, original) for existing, _ in chosen
        ):
            continue
        chosen.append((original, synonyms))

    # An alternative that contains another group's original would be rewritten a
    # second time by that group's pattern, chaining unrelated replacements.
    all_originals = [original for original, _ in chosen]
    groups: list[list[str]] = []
    for original, synonyms in chosen:
        safe = [
            synonym
            for synonym in synonyms
            if not any(_contains(original, synonym) or _contains(synonym, other)
                       for other in all_originals)
        ]
        if safe:
            groups.append([original, *safe])
        if len(groups) >= max_groups:
            break

    return groups


def generate_synonym_groups_from_text(
    prose: str,
    *,
    lang: str = "en",
    max_groups: int = MAX_GROUPS,
    model: str | None = None,
    host: str | None = None,
) -> list[list[str]]:
    """Return validated synonym groups for a document's prose.

    ``prose`` is plain visible text, not HTML: the model needs sentences to judge
    grammar and meaning, and markup only wastes its context window.
    """
    prose = prose.strip()
    if not prose:
        return []

    resolved_model = _model(model)
    digest = hashlib.sha256(
        f"{resolved_model}\x00{lang}\x00{prose}".encode("utf-8")
    ).hexdigest()
    cache_key = (resolved_model, digest)
    if cache_key in _CACHE:
        return [list(group) for group in _CACHE[cache_key]]

    prompt = _PROMPT_TEMPLATE.format(
        max_synonyms=MAX_SYNONYMS,
        max_groups=max_groups,
        target_groups=max(6, min(14, max_groups)),
        language=_language_name(lang),
        document=prose,
    )

    response = _post_json(
        "/api/generate",
        {
            "model": resolved_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": TEMPERATURE, "num_predict": 2048},
        },
        host=host,
        model=resolved_model,
    )

    raw = str(response.get("response", "")).strip()
    if not raw:
        raise SynonymDataUnavailable(
            "Ollama returned an empty response. The model may still be loading; retry, "
            "or use a smaller OLLAMA_MODEL."
        )

    groups = _parse_groups(raw, prose, max_groups=max_groups)
    _CACHE[cache_key] = [list(group) for group in groups]
    return groups


def discover_synonyms(
    term: str, *, lang: str = "en", max_alternatives: int = MAX_SYNONYMS
) -> list[str]:
    """Return alternatives for a single ``term``, judged without sentence context.

    Prefer :func:`generate_synonym_groups_from_text`; this exists for callers that
    only have a bare word, and is inherently less reliable because the model
    cannot see which sense is meant.
    """
    normalized = _normalize_word(term)
    if not normalized or " " in normalized:
        return []

    groups = generate_synonym_groups_from_text(
        normalized, lang=lang, max_groups=1
    )
    if not groups:
        return []
    return groups[0][1 : 1 + max_alternatives]


def generate_synonym_groups(
    seed_terms: object, *, lang: str = "en", model: str | None = None, host: str | None = None
) -> list[list[str]]:
    """Return synonym groups for ``seed_terms``.

    Accepts an iterable of words or a single string of prose. Given bare words the
    model has no sentence context, so this is the weaker entry point; pass prose
    whenever it is available.
    """
    if isinstance(seed_terms, str):
        return generate_synonym_groups_from_text(
            seed_terms, lang=lang, model=model, host=host
        )

    terms = [str(term) for term in seed_terms]  # type: ignore[union-attr]
    if not terms:
        return []
    return generate_synonym_groups_from_text(
        " ".join(terms), lang=lang, model=model, host=host
    )