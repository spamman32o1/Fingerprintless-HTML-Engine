from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from importlib import import_module
from typing import Protocol


class SynonymProvider(Protocol):
    """Interface for synonym providers."""

    def discover(self, term: str) -> set[str]:
        """Return synonyms for a single term."""


def _normalize_token(token: str) -> str:
    token = token.strip().lower()
    token = re.sub(r"[_\-]+", " ", token)
    token = re.sub(r"\s+", " ", token)
    return token


def _normalize_terms(terms: Iterable[str]) -> set[str]:
    normalized: set[str] = set()
    for term in terms:
        cleaned = _normalize_token(term)
        if cleaned:
            normalized.add(cleaned)
    return normalized


def aggregate_synonyms(term: str, providers: Sequence[SynonymProvider]) -> set[str]:
    """Merge normalized synonyms from all providers for a term."""
    merged: set[str] = {_normalize_token(term)}
    for provider in providers:
        try:
            merged.update(_normalize_terms(provider.discover(term)))
        except Exception:
            continue
    merged.discard("")
    return merged


@dataclass(frozen=True)
class WordNetProvider:
    """Synonyms via NLTK WordNet."""

    importer: Callable[[str], object] = import_module

    def discover(self, term: str) -> set[str]:
        try:
            wn = self.importer("nltk.corpus.wordnet")
        except Exception:
            return set()

        synonyms: set[str] = set()
        for synset in wn.synsets(term):
            for lemma in synset.lemmas():
                synonyms.add(lemma.name())
        return synonyms


@dataclass(frozen=True)
class PyDictionaryProvider:
    """Synonyms via PyDictionary."""

    importer: Callable[[str], object] = import_module

    def discover(self, term: str) -> set[str]:
        try:
            module = self.importer("PyDictionary")
            dictionary = module.PyDictionary()
            result = dictionary.synonym(term)
        except Exception:
            return set()

        if not result:
            return set()
        if isinstance(result, list):
            return {str(item) for item in result}
        return set()


@dataclass(frozen=True)
class SpacySimilarityProvider:
    """Synonyms via spaCy token vectors/similarity."""

    nlp_model: str = "en_core_web_md"
    top_n: int = 10
    similarity_threshold: float = 0.6
    import_spacy: Callable[[str], object] = import_module

    def discover(self, term: str) -> set[str]:
        try:
            spacy = self.import_spacy("spacy")
            nlp = spacy.load(self.nlp_model)
        except Exception:
            return set()

        try:
            vocab_strings = [s for s in nlp.vocab.strings if s and " " not in s and s.isalpha()]
            if not vocab_strings:
                return set()
            term_token = nlp(term)
            if not term_token.vector_norm:
                return set()

            scored: list[tuple[str, float]] = []
            for candidate in vocab_strings:
                candidate_doc = nlp(candidate)
                if not candidate_doc.vector_norm:
                    continue
                score = term_token.similarity(candidate_doc)
                if score >= self.similarity_threshold:
                    scored.append((candidate, score))

            scored.sort(key=lambda item: item[1], reverse=True)
            return {word for word, _ in scored[: self.top_n]}
        except Exception:
            return set()


@dataclass(frozen=True)
class Word2VecProvider:
    """Synonyms via gensim KeyedVectors."""

    model_path: str
    top_n: int = 10
    similarity_threshold: float = 0.6
    importer: Callable[[str], object] = import_module

    def discover(self, term: str) -> set[str]:
        try:
            models = self.importer("gensim.models")
            keyed_vectors = models.KeyedVectors.load(self.model_path, mmap="r")
        except Exception:
            return set()

        try:
            similar = keyed_vectors.most_similar(term, topn=self.top_n)
        except Exception:
            return set()

        return {word for word, score in similar if score >= self.similarity_threshold}


@dataclass(frozen=True)
class HeuristicDictionaryProvider:
    """Simple local dictionary + string heuristics fallback."""

    dictionary: dict[str, Sequence[str]] | None = None

    def discover(self, term: str) -> set[str]:
        normalized = _normalize_token(term)
        if not normalized:
            return set()

        defaults = {
            "fast": ["quick", "rapid", "swift"],
            "small": ["tiny", "compact", "miniature"],
            "big": ["large", "huge", "giant"],
        }
        combined = dict(defaults)
        if self.dictionary:
            combined.update({
                _normalize_token(key): [_normalize_token(item) for item in value]
                for key, value in self.dictionary.items()
            })

        direct = set(combined.get(normalized, []))

        heuristic = {
            normalized.replace("ise", "ize") if "ise" in normalized else "",
            normalized.replace("ize", "ise") if "ize" in normalized else "",
            normalized.replace("our", "or") if "our" in normalized else "",
            normalized.replace("or", "our") if normalized.endswith("or") else "",
        }

        return {word for word in direct.union(heuristic) if word and word != normalized}


def generate_synonym_groups(
    seed_terms: list[str],
    enabled_providers: Sequence[SynonymProvider] | None = None,
) -> list[list[str]]:
    """Return normalized synonym groups compatible with build_synonym_patterns()."""
    providers: Sequence[SynonymProvider]
    if enabled_providers is None:
        providers = (
            WordNetProvider(),
            PyDictionaryProvider(),
            SpacySimilarityProvider(),
            HeuristicDictionaryProvider(),
        )
    else:
        providers = enabled_providers

    groups: list[list[str]] = []
    seen_groups: set[frozenset[str]] = set()

    for term in seed_terms:
        merged = aggregate_synonyms(term, providers)
        if len(merged) < 2:
            continue

        frozen = frozenset(merged)
        if frozen in seen_groups:
            continue

        seen_groups.add(frozen)
        groups.append(sorted(merged))

    return groups
