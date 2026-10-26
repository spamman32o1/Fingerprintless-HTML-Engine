from __future__ import annotations

import argparse
import html as _html_mod
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Sequence

from .html_utils import encode_quoted_printable_html, extract_lang, sanitize_input_html
from .image_utils import RemoteImageCache
from .io_utils import _collect_input_files, _prompt_yes_no, prompt_int, read_text_with_fallback
from .models import Opt
from .synonym_discovery import (
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_HOST,
    SynonymDataUnavailable,
    check_available,
    generate_synonym_groups,
)
from .text_utils import build_synonym_patterns, parse_synonym_lines
from .variant import build_variant, random_title


class _Ansi:
    RESET = "\033[0m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    MAGENTA = "\033[95m"


def _colorize(text: str, color: str) -> str:
    return f"{color}{text}{_Ansi.RESET}"


def _prompt_text(icon: str, text: str) -> str:
    return f"{_colorize(icon, _Ansi.BLUE)} {_colorize(text, _Ansi.CYAN)}"


def _status_text(icon: str, text: str, color: str = _Ansi.GREEN) -> str:
    return f"{_colorize(icon, _Ansi.BLUE)} {_colorize(text, color)}"


def _print_startup_banner() -> None:
    banner_lines = [
        "╔══════════════════════════════════════════════════════════════╗",
        "║  ███████╗██╗███╗   ██╗ ██████╗ ███████╗██████╗ ██████╗      ║",
        "║  ██╔════╝██║████╗  ██║██╔════╝ ██╔════╝██╔══██╗██╔══██╗     ║",
        "║  █████╗  ██║██╔██╗ ██║██║  ███╗█████╗  ██████╔╝██████╔╝     ║",
        "║  ██╔══╝  ██║██║╚██╗██║██║   ██║██╔══╝  ██╔══██╗██╔══██╗     ║",
        "║  ██║     ██║██║ ╚████║╚██████╔╝███████╗██║  ██║██║  ██║     ║",
        "║  ╚═╝     ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝     ║",
        "╚══════════════════════════════════════════════════════════════╝",
    ]
    for line in banner_lines:
        print(_colorize(line, _Ansi.MAGENTA))
    print(_colorize("              ✨ Fingerprint-less HTML Engine ✨", _Ansi.CYAN))
    print()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Input HTML encoding (default: utf-8; on decode error retries latin-1 then windows-1252).",
    )
    parser.add_argument(
        "--ie-conditional-comments",
        action="store_true",
        dest="ie_condition_randomize",
        help="Opt into randomized IE conditional comments (disabled by default).",
    )
    parser.add_argument(
        "--no-ie-conditional-comments",
        action="store_false",
        dest="ie_condition_randomize",
        help="Disable randomized IE conditional comments.",
    )
    parser.add_argument(
        "--no-structure-randomize",
        action="store_false",
        dest="structure_randomize",
        help="Disable safe wrapper structure randomization.",
    )
    parser.add_argument(
        "--max-nesting",
        type=int,
        default=None,
        help="Base maximum nesting depth for wrapper divs (default: 4).",
    )
    parser.add_argument(
        "--max-nesting-jitter",
        type=int,
        default=0,
        help="Random +/- jitter applied to max nesting per variant (default: 0).",
    )
    parser.add_argument(
        "--no-dark-mode",
        action="store_false",
        dest="allow_dark_mode",
        help="Disable dark theme styling.",
    )
    parser.add_argument(
        "--no-css-randomization",
        action="store_false",
        dest="enable_css_randomization",
        help="Disable source-relative CSS value and typography jitter.",
    )
    parser.add_argument(
        "--no-font-randomization",
        action="store_false",
        dest="enable_font_randomization",
        help="Disable fallback font-stack selection for unstyled fragments.",
    )
    parser.add_argument(
        "--no-font-css",
        action="store_false",
        dest="enable_font_css",
        help="Disable typography-related CSS (font family, sizes, spacing, and line height).",
    )
    parser.add_argument(
        "--no-font-features",
        action="store_false",
        dest="enable_font_features",
        help="Disable advanced font features (variation settings, optical sizing, kerning, and stretch).",
    )
    parser.add_argument(
        "--no-gradients",
        action="store_false",
        dest="enable_gradients",
        help="Disable gradient background selection.",
    )
    parser.add_argument(
        "--no-noise-textures",
        action="store_false",
        dest="enable_noise_textures",
        help="Disable noise texture background overlays.",
    )
    parser.add_argument(
        "--no-color-palette-randomization",
        action="store_false",
        dest="enable_color_palette_randomization",
        help="Disable bounded source-color jitter; preserve original colors.",
    )
    parser.add_argument(
        "--no-span-wrap",
        action="store_false",
        dest="enable_span_wrapping",
        help="Disable span wrapping in text nodes.",
    )
    parser.add_argument(
        "--no-wrapper-nesting",
        action="store_false",
        dest="enable_wrapper_nesting",
        help="Disable randomized wrapper nesting around content.",
    )
    parser.add_argument(
        "--no-layout-randomization",
        action="store_false",
        dest="enable_layout_randomization",
        help="Disable randomized layout table selection and placement.",
    )
    parser.add_argument(
        "--no-layout-tables",
        action="store_true",
        dest="disable_layout_tables",
        help="Disable layout table wrappers (forces plain layout container).",
    )
    parser.add_argument(
        "--no-wrapper-styles",
        action="store_true",
        dest="disable_wrapper_styles",
        help="Disable wrapper padding/margin/border/box-shadow styles.",
    )
    parser.add_argument(
        "--no-body-styles",
        action="store_false",
        dest="enable_body_styles",
        help="Disable body-level styling rules (no body styles or background rendering).",
    )
    parser.add_argument(
        "--no-image-inlining",
        action="store_false",
        dest="enable_image_inlining",
        help="Disable preprocessing that inlines remote image references as data URLs.",
    )
    parser.add_argument(
        "--no-remote-image-cache",
        action="store_false",
        dest="enable_remote_image_cache",
        help="Disable reuse of downloaded remote image payloads across references within a run.",
    )
    parser.add_argument(
        "--pretty-output",
        action="store_true",
        dest="pretty_output",
        default=None,
        help="Pretty-print output HTML with indentation and newlines (defaults on in Libero mode).",
    )
    parser.add_argument(
        "--no-pretty-output",
        action="store_false",
        dest="pretty_output",
        default=None,
        help="Disable pretty-print output formatting (overrides Libero default).",
    )
    parser.add_argument(
        "--generate-synonyms",
        action="store_true",
        default=True,
        dest="generate_synonyms",
        help="Enable automatic synonym map generation (default).",
    )
    parser.add_argument(
        "--no-generate-synonyms",
        action="store_false",
        default=True,
        dest="generate_synonyms",
        help="Disable automatic synonym map generation.",
    )
    parser.add_argument(
        "--ollama-host",
        default=None,
        dest="ollama_host",
        metavar="URL",
        help=(
            "Ollama endpoint used for synonym generation "
            f"(default: ${'OLLAMA_HOST'} or {DEFAULT_OLLAMA_HOST})."
        ),
    )
    parser.add_argument(
        "--synonym-model",
        default=None,
        dest="synonym_model",
        metavar="NAME",
        help=f"Ollama model used for synonym generation (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--write-generated-synonym-map",
        action="store_true",
        default=None,
        dest="write_generated_synonym_map",
        help="Write generated synonym groups to a reusable pipe-delimited map file.",
    )
    parser.add_argument(
        "--no-write-generated-synonym-map",
        action="store_false",
        default=None,
        dest="write_generated_synonym_map",
        help="Do not write generated synonym groups to disk.",
    )
    parser.add_argument(
        "--generated-synonym-map-filename",
        default="generated_synonym_map.txt",
        dest="generated_synonym_map_filename",
        help="Filename to use when writing the generated synonym map (default: generated_synonym_map.txt).",
    )
    parser.set_defaults(
        ie_condition_randomize=True,
        structure_randomize=True,
        enable_image_inlining=True,
        enable_remote_image_cache=True,
    )
    return parser


#: Matches base64 data URIs so their encoded payload never reaches the model. The
#: payload is letters/digits only and would otherwise crowd out the real sentences.
_BASE64_DATA_URI_RE = re.compile(r"data:[^,]*;base64,[A-Za-z0-9+/=]+", re.IGNORECASE)

#: Matches a tag, a closing tag, a comment, a doctype, or a declaration.
_TAG_OR_DECL_RE = re.compile(r"<[^>]+>")

#: Matches an entire ``<style>``/``<script>`` element including its body. Their
#: content is CSS/JavaScript, never prose, and stripping only the tags leaves the
#: CSS property names (``margin``, ``font-family``, ``!important``) behind.
_RAW_TEXT_BLOCK_RE = re.compile(r"<(style|script|title|textarea)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)

#: Block-level tags, which mark a visual break. They become newlines so adjacent
#: sentences and list items stay separate after the tags themselves are removed.
_BLOCK_TAG_RE = re.compile(
    r"</?(?:p|div|br|tr|td|th|li|ul|ol|h[1-6]|table|tbody|thead|blockquote|hr|section|article|header|footer)\b[^>]*>",
    re.IGNORECASE,
)

#: Attributes whose values are machine content (base64 payloads, URLs) rather than
#: prose. They are stripped before tokenization so encoded data never leaks in.
_ATTR_RE = re.compile(r"(?:src|href|url|data|alt|value)\s*=\s*\"[^\"]*\"|(?:src|href|url|data|alt|value)\s*=\s*'[^']*'|(?:src|href|url|data|alt|value)\s*=\s*[^\s>]+", re.IGNORECASE)


def extract_document_prose(text_blocks: Iterable[str]) -> str:
    """Return the visible prose of an HTML document as plain text.

    The synonym pass is context-dependent: the model must read real sentences to
    tell a verb from a noun and to notice that a word is part of a product name.
    So this returns sentences rather than a bag of tokens, with everything that is
    not prose removed first:

    * base64 data URIs, whose payload would otherwise dominate the text;
    * whole ``<style>``/``<script>``/``<title>``/``<textarea>`` blocks, whose
      content is CSS/JS and whose leftover property names read as English;
    * machine-content attribute values such as ``src`` and ``href``;
    * all remaining tags and declarations;
    * HTML entities, decoded to their characters so ``&bull;`` does not become a
      word.

    Block-level tags are turned into newlines before removal so sentence
    boundaries and list items stay separated instead of running together.
    """
    chunks: list[str] = []
    for text in text_blocks:
        text = _BASE64_DATA_URI_RE.sub(" ", text)
        text = _ATTR_RE.sub(" ", text)
        text = _RAW_TEXT_BLOCK_RE.sub(" ", text)
        # Preserve structure: block boundaries become line breaks, and inline tags
        # are deleted without a separator so a word split across tags ("Secu<b>rity")
        # is not torn into two words.
        text = _BLOCK_TAG_RE.sub("\n", text)
        text = _TAG_OR_DECL_RE.sub("", text)
        text = _html_mod.unescape(text)
        text = re.sub(r"&[A-Za-z0-9#]+;", " ", text)
        chunks.append(text)

    # Collapse the whitespace the tag removal introduced, keeping line structure.
    prose_lines: list[str] = []
    for line in "\n".join(chunks).splitlines():
        collapsed = re.sub(r"[ \t\f\v]+", " ", line).strip()
        if collapsed:
            prose_lines.append(collapsed)
    return "\n".join(prose_lines)


def _merge_synonym_groups(*group_sets: Sequence[Sequence[str]]) -> list[list[str]]:
    merged: list[list[str]] = []
    seen_groups: set[frozenset[str]] = set()
    for groups in group_sets:
        for group in groups:
            normalized: list[str] = []
            seen_terms: set[str] = set()
            for term in group:
                token = term.strip()
                lowered = token.lower()
                if not token or lowered in seen_terms:
                    continue
                seen_terms.add(lowered)
                normalized.append(token)
            if len(normalized) < 2:
                continue
            key = frozenset(term.lower() for term in normalized)
            if key in seen_groups:
                continue
            seen_groups.add(key)
            merged.append(normalized)
    return merged


def _serialize_synonym_groups(groups: Sequence[Sequence[str]]) -> str:
    lines = [" | ".join(term.strip() for term in group if term.strip()) for group in groups]
    return "\n".join(line for line in lines if line)


def _write_generated_synonym_map_files(
    output_directories: Sequence[Path],
    groups: Sequence[Sequence[str]],
    *,
    filename: str,
) -> list[Path]:
    normalized_filename = Path(filename).name or "generated_synonym_map.txt"
    serialized = _serialize_synonym_groups(groups)
    written_paths: list[Path] = []
    seen: set[Path] = set()
    for directory in output_directories:
        resolved = directory.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        target = resolved / normalized_filename
        target.write_text(f"{serialized}\n", encoding="utf-8")
        written_paths.append(target)
    return written_paths


def _prompt_output_mode() -> str:
    print(_status_text("🎨", "Select output mode:", _Ansi.MAGENTA))
    print(_status_text("•", "1) default", _Ansi.CYAN))
    print(_status_text("•", "2) strict", _Ansi.CYAN))
    print(_status_text("•", "3) super strict", _Ansi.CYAN))
    print(_status_text("•", "4) libero", _Ansi.CYAN))
    while True:
        choice = input(_prompt_text("❓", "Choose mode [1-4] (default 1): ")).strip()
        if choice == "":
            return "default"
        if choice == "1":
            return "default"
        if choice == "2":
            return "strict"
        if choice == "3":
            return "super_strict"
        if choice == "4":
            return "libero"
        print(_status_text("⚠️", "Please enter 1, 2, 3, or 4.", _Ansi.YELLOW))


def main() -> None:
    _print_startup_banner()
    parser = _build_parser()
    args = parser.parse_args()

    input_paths = _collect_input_files()

    input_encoding = args.encoding.strip().lower() if args.encoding else "utf-8"

    count = prompt_int(_prompt_text("🔢", "How many variants? "), lo=1)

    generate_synonyms = args.generate_synonyms

    # Fail before the first document rather than part-way through a run: reaching a
    # stopped daemon or an unpulled model after minutes of work is a worse
    # experience than a clear message up front.
    if generate_synonyms:
        try:
            check_available(model=args.synonym_model, host=args.ollama_host)
        except SynonymDataUnavailable as exc:
            print(_status_text("❌", str(exc), _Ansi.YELLOW))
            return 1

    synonym_lines: List[str] = []
    synonym_path = ""
    while True:
        if not synonym_path:
            synonym_path = input(
                _prompt_text("📄", "Optional synonym map file path (pipe-separated synonyms per line, blank to skip): ")
            ).strip().strip('"').strip("'")
        if not synonym_path:
            break
        path = Path(synonym_path)
        try:
            raw_synonyms = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(_status_text("❌", f"Could not read synonym map file '{path}': {exc}", _Ansi.YELLOW))
            retry = input(_prompt_text("↩️", "Press Enter to skip or type a new path to retry: ")).strip()
            if retry:
                synonym_path = retry
                continue
            break
        synonym_lines = [line.strip() for line in raw_synonyms.splitlines() if line.strip()]
        break
    file_synonym_groups = parse_synonym_lines(synonym_lines)

    write_generated_synonym_map = args.write_generated_synonym_map
    if write_generated_synonym_map is None:
        write_generated_synonym_map = bool(generate_synonyms)

    generated_synonym_groups: list[list[str]] = []

    base_max_nesting = args.max_nesting
    if base_max_nesting is None:
        base_max_nesting = Opt(count=count).max_nesting

    output_mode = _prompt_output_mode()
    libero_mode = output_mode == "libero"
    pretty_output = args.pretty_output
    if pretty_output is None:
        pretty_output = libero_mode

    opt = Opt(
        count=count,
        ie_condition_randomize=args.ie_condition_randomize,
        structure_randomize=args.structure_randomize,
        max_nesting=base_max_nesting,
        max_nesting_jitter=max(0, args.max_nesting_jitter),
        output_mode=output_mode,
        allow_dark_mode=args.allow_dark_mode,
        enable_css_randomization=args.enable_css_randomization,
        enable_font_css=args.enable_font_css,
        enable_font_randomization=args.enable_font_randomization,
        enable_font_features=args.enable_font_features,
        enable_gradients=args.enable_gradients,
        enable_noise_textures=args.enable_noise_textures,
        enable_color_palette_randomization=args.enable_color_palette_randomization,
        enable_span_wrapping=args.enable_span_wrapping,
        enable_wrapper_nesting=args.enable_wrapper_nesting,
        enable_layout_randomization=args.enable_layout_randomization,
        enable_body_styles=args.enable_body_styles,
        enable_image_inlining=args.enable_image_inlining,
        enable_remote_image_cache=args.enable_remote_image_cache,
        disable_layout_tables=args.disable_layout_tables,
        disable_wrapper_styles=args.disable_wrapper_styles,
        pretty_output=pretty_output,
    )
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path_mode = "single"
    if len(input_paths) > 1:
        use_same = _prompt_yes_no(
            _prompt_text("🗂️", "Multiple input files detected. Use the same output folder for all? y/n (default y): "),
            default=True,
        )
        output_path_mode = "same" if use_same else "different"

    base_outdir = Path(f"variants_{ts}")
    if output_path_mode in {"single", "same"}:
        base_outdir.mkdir(parents=True, exist_ok=True)

    rng = random.Random()
    image_cache = None
    if opt.enable_image_inlining and opt.enable_remote_image_cache:
        image_cache = RemoteImageCache(enabled=True)

    def _sanitize_token(value: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)
        cleaned = cleaned.strip("_")
        return cleaned or "input"

    filename_prefixes: dict[Path, str] = {}
    if output_path_mode == "same":
        stem_counts: dict[str, int] = {}
        for input_path in input_paths:
            stem_counts[input_path.stem] = stem_counts.get(input_path.stem, 0) + 1

        prefix_seen: dict[str, int] = {}
        for input_path in input_paths:
            stem = input_path.stem
            if stem_counts[stem] == 1:
                prefix = f"{stem}_"
            else:
                parent_token = _sanitize_token(input_path.parent.name or "root")
                prefix = f"{stem}_{parent_token}_"

            count = prefix_seen.get(prefix, 0)
            if count:
                prefix = f"{prefix}{count + 1}_"
            prefix_seen[prefix] = count + 1
            filename_prefixes[input_path] = prefix

    output_locations: list[Path] = []
    generated_documents: set[str] = set()

    def _build_libero_html(html_text: str) -> str:
        return encode_quoted_printable_html(
            html_text,
            include_headers=False,
            tag_mode="safe",
            maxlinelen=None,
        )

    for input_path in input_paths:
        raw_html = read_text_with_fallback(input_path, input_encoding)
        sanitized = sanitize_input_html(raw_html)
        lang = extract_lang(sanitized, fallback_lang="it" if opt.output_mode == "libero" else "en")

        # Synonyms are generated per document, in that document's own language.
        # A single global pass would apply one language's lexicon to every file.
        per_file_groups = list(file_synonym_groups)
        if generate_synonyms:
            # The model is given the document's prose, not a bag of words: judging
            # grammar and sense needs sentences.
            prose = extract_document_prose([sanitized])
            try:
                per_file_groups = _merge_synonym_groups(
                    per_file_groups,
                    generate_synonym_groups(prose, lang=lang, model=args.synonym_model),
                )
            except SynonymDataUnavailable as exc:
                print(_status_text("❌", str(exc), _Ansi.YELLOW))
                return 1
        synonym_patterns = build_synonym_patterns(per_file_groups)
        generated_synonym_groups.extend(per_file_groups)
        print(
            _status_text(
                "ℹ️",
                f"Synonyms for {input_path.name} [{lang}]: {len(per_file_groups)} groups",
            )
        )

        if output_path_mode == "different":
            outdir = Path(f"variants_{ts}_{input_path.stem}")
            outdir.mkdir(parents=True, exist_ok=True)
            filename_prefix = ""
        else:
            outdir = base_outdir
            filename_prefix = filename_prefixes.get(input_path, f"{input_path.stem}_")

        for i in range(1, opt.count + 1):
            # Identity is checked after final encoding, not inferred from CSS differences.
            for _attempt in range(32):
                variant_title = random_title()
                variant = build_variant(
                    rng,
                    sanitized,
                    opt,
                    i,
                    lang,
                    variant_title,
                    synonym_patterns,
                    image_cache=image_cache,
                )
                if opt.output_mode == "libero":
                    variant = _build_libero_html(variant)
                if variant not in generated_documents:
                    generated_documents.add(variant)
                    break
            else:
                raise RuntimeError(f"Unable to produce a unique variant for {input_path.name} at index {i}")
            output_name = f"{filename_prefix}variant_{i:03d}.html"
            (outdir / output_name).write_text(variant, encoding="utf-8")

        output_locations.append(outdir.resolve())

    if output_path_mode == "same":
        print(
            _status_text(
                "✅",
                f"Done. Wrote {opt.count * len(input_paths)} files to: {base_outdir.resolve()}",
            )
        )
    else:
        for outdir in output_locations:
            print(_status_text("✅", f"Done. Wrote {opt.count} files to: {outdir}"))

    if generated_synonym_groups and write_generated_synonym_map:
        written_map_paths = _write_generated_synonym_map_files(
            output_locations,
            generated_synonym_groups,
            filename=args.generated_synonym_map_filename,
        )
        for path in written_map_paths:
            print(_status_text("📝", f"Generated synonym map written to: {path}"))


__all__ = ["main"]
