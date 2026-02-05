from __future__ import annotations

from pathlib import Path

import pytest

from fingerprintless_html_engine import cli
from fingerprintless_html_engine.cli import (
    _build_parser,
    _create_synonym_providers,
    _merge_synonym_groups,
    _parse_provider_names,
    _serialize_synonym_groups,
    _write_generated_synonym_map_files,
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


def test_build_parser_supports_generated_synonym_map_output_flags() -> None:
    parser = _build_parser()

    args = parser.parse_args(["--write-generated-synonym-map"])
    assert args.write_generated_synonym_map is True

    args = parser.parse_args(["--no-write-generated-synonym-map"])
    assert args.write_generated_synonym_map is False

    args = parser.parse_args(["--generated-synonym-map-filename", "my_map.txt"])
    assert args.generated_synonym_map_filename == "my_map.txt"


def test_serialize_synonym_groups_uses_pipe_delimited_parser_compatible_format() -> None:
    serialized = _serialize_synonym_groups([["fast", "quick", "rapid"], ["small", "tiny"]])

    assert serialized == "fast | quick | rapid\nsmall | tiny"


def test_write_generated_synonym_map_files_writes_deduplicated_directories(tmp_path: Path) -> None:
    outdir = tmp_path / "variants"
    outdir.mkdir()

    paths = _write_generated_synonym_map_files(
        [outdir, outdir],
        [["fast", "quick"], ["small", "tiny"]],
        filename="generated_synonym_map.txt",
    )

    assert len(paths) == 1
    assert paths[0].read_text(encoding="utf-8") == "fast | quick\nsmall | tiny\n"


def test_main_skips_generated_map_file_when_write_flag_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "input.html"
    input_file.write_text("<html><body>Fast car</body></html>", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(cli, "_collect_input_files", lambda: [input_file])
    monkeypatch.setattr(cli, "prompt_int", lambda *args, **kwargs: 1)
    monkeypatch.setattr(cli, "_prompt_yes_no", lambda *args, **kwargs: False)
    monkeypatch.setattr(cli, "read_text_with_fallback", lambda *args, **kwargs: input_file.read_text(encoding="utf-8"))
    monkeypatch.setattr(cli, "build_variant", lambda *args, **kwargs: "<html><body>Variant</body></html>")
    monkeypatch.setattr(cli, "generate_synonym_groups", lambda *args, **kwargs: [["fast", "quick"]])
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: "")
    monkeypatch.setattr(
        "sys.argv",
        ["prog", "--generate-synonyms", "--no-write-generated-synonym-map"],
    )

    cli.main()

    variant_dirs = list(tmp_path.glob("variants_*"))
    assert len(variant_dirs) == 1
    assert (variant_dirs[0] / "generated_synonym_map.txt").exists() is False


def test_main_writes_generated_map_file_when_generation_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_file = tmp_path / "input.html"
    input_file.write_text("<html><body>Fast car</body></html>", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(cli, "_collect_input_files", lambda: [input_file])
    monkeypatch.setattr(cli, "prompt_int", lambda *args, **kwargs: 1)
    monkeypatch.setattr(cli, "_prompt_yes_no", lambda *args, **kwargs: False)
    monkeypatch.setattr(cli, "read_text_with_fallback", lambda *args, **kwargs: input_file.read_text(encoding="utf-8"))
    monkeypatch.setattr(cli, "build_variant", lambda *args, **kwargs: "<html><body>Variant</body></html>")
    monkeypatch.setattr(cli, "generate_synonym_groups", lambda *args, **kwargs: [["fast", "quick", "rapid"]])
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: "")
    monkeypatch.setattr("sys.argv", ["prog", "--generate-synonyms"])

    cli.main()

    variant_dirs = list(tmp_path.glob("variants_*"))
    assert len(variant_dirs) == 1
    generated_map = variant_dirs[0] / "generated_synonym_map.txt"
    assert generated_map.read_text(encoding="utf-8") == "fast | quick | rapid\n"

    stdout = capsys.readouterr().out
    assert f"Generated synonym map written to: {generated_map}" in stdout
