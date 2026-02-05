from __future__ import annotations

from fingerprintless_html_engine.synonym_discovery import (
    HeuristicDictionaryProvider,
    PyDictionaryProvider,
    WordNetProvider,
    aggregate_synonyms,
    generate_synonym_groups,
)


class _StaticProvider:
    def __init__(self, terms: set[str]) -> None:
        self._terms = terms

    def discover(self, term: str) -> set[str]:
        return self._terms


class _MapProvider:
    def __init__(self, mapping: dict[str, set[str]]) -> None:
        self._mapping = mapping

    def discover(self, term: str) -> set[str]:
        return self._mapping.get(term.lower(), set())


class _FailingProvider:
    def discover(self, term: str) -> set[str]:
        raise RuntimeError("provider failed")


def test_aggregate_synonyms_normalizes_and_deduplicates() -> None:
    providers = [
        _StaticProvider({"Quick", "rapid", "well-known", ""}),
        _StaticProvider({"  QUICK  ", "well_known"}),
    ]

    merged = aggregate_synonyms("Fast", providers)

    assert merged == {"fast", "quick", "rapid", "well known"}


def test_generate_synonym_groups_drops_singletons_and_deduplicates_groups() -> None:
    provider = _MapProvider({"fast": {"fast", "quick"}})

    groups = generate_synonym_groups(["fast", "FAST", "solo"], enabled_providers=[provider])

    assert groups == [["fast", "quick"]]


def test_generate_synonym_groups_handles_provider_errors_gracefully() -> None:
    groups = generate_synonym_groups(
        ["small"],
        enabled_providers=[_FailingProvider(), HeuristicDictionaryProvider()],
    )

    assert groups == [["compact", "miniature", "small", "tiny"]]


def test_wordnet_provider_returns_empty_when_dependency_missing() -> None:
    provider = WordNetProvider(importer=lambda _: (_ for _ in ()).throw(ImportError("missing")))

    assert provider.discover("fast") == set()


def test_pydictionary_provider_returns_empty_when_dependency_missing() -> None:
    provider = PyDictionaryProvider(importer=lambda _: (_ for _ in ()).throw(ImportError("missing")))

    assert provider.discover("fast") == set()
