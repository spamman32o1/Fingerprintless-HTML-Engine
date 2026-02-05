from __future__ import annotations

import pytest

from fingerprintless_html_engine.cli import (
    _build_parser,
    _create_synonym_providers,
    _merge_synonym_groups,
    _parse_provider_names,
)
from fingerprintless_html_engine.synonym_discovery import (
    HeuristicDictionaryProvider,
    PyDictionaryProvider,
    WordNetProvider,
)


def test_build_parser_supports_generate_synonym_flags() -> None:
    parser = _build_parser()

    args = parser.parse_args(["--generate-synonyms"])
    assert args.generate_synonyms is True

    args = parser.parse_args(["--no-generate-synonyms"])
    assert args.generate_synonyms is False


def test_parse_provider_names_accepts_repeatable_and_csv_values() -> None:
    parsed = _parse_provider_names(["wordnet,pydictionary", "heuristic", "spacy, wordnet"])

    assert parsed == ["wordnet", "pydictionary", "heuristic", "spacy", "wordnet"]


def test_create_synonym_providers_builds_known_provider_instances() -> None:
    providers = _create_synonym_providers(["wordnet", "pydictionary", "heuristic"])

    assert isinstance(providers[0], WordNetProvider)
    assert isinstance(providers[1], PyDictionaryProvider)
    assert isinstance(providers[2], HeuristicDictionaryProvider)


def test_create_synonym_providers_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown synonym provider"):
        _create_synonym_providers(["unknown"])


def test_merge_synonym_groups_combines_sources_and_deduplicates() -> None:
    file_groups = [["Fast", "Quick", "fast"], ["Small", "Tiny"]]
    generated_groups = [["quick", "FAST"], ["Large", "Big", "large"], ["tiny", "small"]]

    merged = _merge_synonym_groups(file_groups, generated_groups)

    assert merged == [["Fast", "Quick"], ["Small", "Tiny"], ["Large", "Big"]]
