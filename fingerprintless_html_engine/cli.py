from __future__ import annotations

import argparse
import random
from datetime import datetime
from pathlib import Path
from typing import List

from .html_utils import extract_body_content, extract_lang, sanitize_input_html
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
    parser.set_defaults(ie_condition_randomize=True, structure_randomize=True)
    args = parser.parse_args()

    input_paths = _collect_input_files()

    input_encoding = args.encoding.strip().lower() if args.encoding else "utf-8"

    count = prompt_int("How many variants? ", lo=1)

    synonym_lines: List[str] = []
    while True:
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

    opt = Opt(
        count=count,
        ie_condition_randomize=args.ie_condition_randomize,
        structure_randomize=args.structure_randomize,
    )
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_mode = "single"
    if len(input_paths) > 1:
        use_same = _prompt_yes_no(
            "Multiple input files detected. Use the same output folder for all? y/n (default y): ",
            default=True,
        )
        output_mode = "same" if use_same else "different"

    base_outdir = Path(f"variants_{ts}")
    if output_mode in {"single", "same"}:
        base_outdir.mkdir(parents=True, exist_ok=True)

    rng = random.Random()

    output_locations: list[Path] = []
    for input_path in input_paths:
        raw_html = read_text_with_fallback(input_path, input_encoding)
        sanitized = sanitize_input_html(raw_html)
        content = extract_body_content(sanitized)
        lang = extract_lang(sanitized)

        if output_mode == "different":
            outdir = Path(f"variants_{ts}_{input_path.stem}")
            outdir.mkdir(parents=True, exist_ok=True)
            filename_prefix = ""
        else:
            outdir = base_outdir
            filename_prefix = f"{input_path.stem}_"

        for i in range(1, opt.count + 1):
            variant_title = random_title()
            variant = build_variant(rng, content, opt, i, lang, variant_title, synonym_patterns)
            (outdir / f"{filename_prefix}variant_{i:03d}.html").write_text(variant, encoding="utf-8")

        output_locations.append(outdir.resolve())

    if output_mode == "same":
        print(f"\nDone. Wrote {opt.count * len(input_paths)} files to: {base_outdir.resolve()}")
    else:
        for outdir in output_locations:
            print(f"\nDone. Wrote {opt.count} files to: {outdir}")


__all__ = ["main"]
