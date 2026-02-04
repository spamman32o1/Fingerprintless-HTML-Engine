from __future__ import annotations

import argparse
import random
from datetime import datetime
from pathlib import Path
from typing import List

from .html_utils import encode_quoted_printable_html, extract_body_content, extract_lang, sanitize_input_html
from .io_utils import _collect_input_files, _prompt_yes_no, prompt_int, read_text_with_fallback
from .models import Opt
from .text_utils import build_synonym_patterns, parse_synonym_lines
from .variant import build_variant, random_title


def main() -> None:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Input HTML encoding (default: utf-8; on decode error retries latin-1 then windows-1252).",
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
        help="Disable randomized CSS styling (forces neutral defaults for colors, fonts, gradients, and textures).",
    )
    parser.add_argument(
        "--no-font-randomization",
        action="store_false",
        dest="enable_font_randomization",
        help="Disable randomized font stack selection.",
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
        help="Disable randomized color palette selection (uses neutral defaults).",
    )
    parser.add_argument(
        "--no-span-wrap",
        action="store_false",
        dest="enable_span_wrapping",
        help="Disable span wrapping in text nodes.",
    )
    parser.add_argument(
        "--no-alt-randomization",
        action="store_false",
        dest="enable_alt_text_randomization",
        help="Disable randomized alt text updates on images.",
    )
    parser.add_argument(
        "--no-meta-noise",
        action="store_false",
        dest="enable_meta_noise",
        help="Disable randomized meta tag noise in the document head.",
    )
    parser.add_argument(
        "--no-jsonld-noise",
        action="store_false",
        dest="enable_jsonld_noise",
        help="Disable fake JSON-LD script noise.",
    )
    parser.add_argument(
        "--no-noise-divs",
        action="store_false",
        dest="enable_noise_divs",
        help="Disable randomized decorative noise divs.",
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
    parser.set_defaults(ie_condition_randomize=True, structure_randomize=True)
    args = parser.parse_args()

    input_paths = _collect_input_files()

    input_encoding = args.encoding.strip().lower() if args.encoding else "utf-8"

    count = prompt_int("How many variants? ", lo=1)

    synonym_lines: List[str] = []
    synonym_path = ""
    while True:
        if not synonym_path:
            synonym_path = input(
                "Optional synonym map file path (pipe-separated synonyms per line, blank to skip): "
            ).strip().strip('"').strip("'")
        if not synonym_path:
            break
        path = Path(synonym_path)
        try:
            raw_synonyms = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(f"Could not read synonym map file '{path}': {exc}")
            retry = input("Press Enter to skip or type a new path to retry: ").strip()
            if retry:
                synonym_path = retry
                continue
            break
        synonym_lines = [line.strip() for line in raw_synonyms.splitlines() if line.strip()]
        break
    synonym_groups = parse_synonym_lines(synonym_lines)
    synonym_patterns = build_synonym_patterns(synonym_groups)

    base_max_nesting = args.max_nesting
    if base_max_nesting is None:
        base_max_nesting = Opt(count=count).max_nesting

    libero_mode = _prompt_yes_no(
        "Enable Libero mode for libero.it (writes quoted-printable strict HTML)? y/n (default n): ",
        default=False,
    )
    output_mode = "libero" if libero_mode else "default"
    if not libero_mode:
        strict_mode = _prompt_yes_no(
            "Enable strict mode (inline styles, no style blocks)? y/n (default n): ",
            default=False,
        )
        output_mode = "strict" if strict_mode else "default"
        if strict_mode:
            super_strict = _prompt_yes_no(
                "Enable super strict mode for aggressive providers? y/n (default n): ",
                default=False,
            )
            if super_strict:
                output_mode = "super_strict"

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
        enable_alt_text_randomization=args.enable_alt_text_randomization,
        enable_meta_noise=args.enable_meta_noise,
        enable_jsonld_noise=args.enable_jsonld_noise,
        enable_noise_divs=args.enable_noise_divs,
        enable_wrapper_nesting=args.enable_wrapper_nesting,
        enable_layout_randomization=args.enable_layout_randomization,
    )
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path_mode = "single"
    if len(input_paths) > 1:
        use_same = _prompt_yes_no(
            "Multiple input files detected. Use the same output folder for all? y/n (default y): ",
            default=True,
        )
        output_path_mode = "same" if use_same else "different"

    base_outdir = Path(f"variants_{ts}")
    if output_path_mode in {"single", "same"}:
        base_outdir.mkdir(parents=True, exist_ok=True)

    rng = random.Random()

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
        content = extract_body_content(sanitized)
        lang = extract_lang(sanitized)

        if output_path_mode == "different":
            outdir = Path(f"variants_{ts}_{input_path.stem}")
            outdir.mkdir(parents=True, exist_ok=True)
            filename_prefix = ""
        else:
            outdir = base_outdir
            filename_prefix = filename_prefixes.get(input_path, f"{input_path.stem}_")

        for i in range(1, opt.count + 1):
            variant_title = random_title()
            variant = build_variant(rng, content, opt, i, lang, variant_title, synonym_patterns)
            if opt.output_mode == "libero":
                variant = _build_libero_html(variant)
                output_name = f"{filename_prefix}variant_{i:03d}.html"
            else:
                output_name = f"{filename_prefix}variant_{i:03d}.html"
            (outdir / output_name).write_text(variant, encoding="utf-8")

        output_locations.append(outdir.resolve())

    if output_path_mode == "same":
        print(f"\nDone. Wrote {opt.count * len(input_paths)} files to: {base_outdir.resolve()}")
    else:
        for outdir in output_locations:
            print(f"\nDone. Wrote {opt.count} files to: {outdir}")


__all__ = ["main"]
