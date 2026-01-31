from __future__ import annotations

import argparse
import random
from datetime import datetime
from pathlib import Path
from typing import List

from .html_utils import (
    encode_quoted_printable_html,
    extract_body_content,
    extract_lang,
    extract_meta_refresh_redirects,
    sanitize_input_html,
)
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

    redirect_entries_by_outdir: dict[Path, dict[str, list[tuple[float, str, str]]]] = {}

    redirect_buckets: list[tuple[str, float | None, float | None]] = [
        ("redirects_wait_le_0.5s.txt", None, 0.5),
        ("redirects_wait_gt_0.5s_le_1.5s.txt", 0.5, 1.5),
        ("redirects_wait_gt_1.5s_le_3s.txt", 1.5, 3.0),
        ("redirects_wait_gt_3s_le_5s.txt", 3.0, 5.0),
        ("redirects_wait_gt_5s_le_10s.txt", 5.0, 10.0),
        ("redirects_wait_gt_10s.txt", 10.0, None),
    ]

    def _bucket_for_delay(delay: float) -> str:
        for filename, lower, upper in redirect_buckets:
            if lower is None and delay <= upper:
                return filename
            if upper is None and delay > lower:
                return filename
            if lower is not None and upper is not None and lower < delay <= upper:
                return filename
        return redirect_buckets[-1][0]

    def _load_redirect_entries(path: Path) -> list[tuple[float, str, str]]:
        if not path.exists():
            return []
        entries: list[tuple[float, str, str]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            delay_str, url, source = parts
            try:
                delay = float(delay_str)
            except ValueError:
                continue
            entries.append((delay, url, source))
        return entries

    def _write_redirect_entries(outdir: Path, entries: dict[str, list[tuple[float, str, str]]]) -> None:
        for filename, _, _ in redirect_buckets:
            bucket_entries = entries.get(filename, [])
            if not bucket_entries:
                continue
            output_file = outdir / filename
            combined = _load_redirect_entries(output_file) + bucket_entries
            combined.sort(key=lambda item: item[0])
            lines = [f"{delay:g}\t{url}\t{source}" for delay, url, source in combined]
            output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

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
            redirects = extract_meta_refresh_redirects(variant)
            if opt.output_mode == "libero":
                variant = _build_libero_html(variant)
                output_name = f"{filename_prefix}variant_{i:03d}.html"
            else:
                output_name = f"{filename_prefix}variant_{i:03d}.html"
            (outdir / output_name).write_text(variant, encoding="utf-8")

            if redirects:
                out_entries = redirect_entries_by_outdir.setdefault(outdir, {})
                source_id = f"{input_path.name}:{output_name}"
                for delay, url in redirects:
                    bucket = _bucket_for_delay(delay)
                    out_entries.setdefault(bucket, []).append((delay, url, source_id))

        output_locations.append(outdir.resolve())

    for outdir, entries in redirect_entries_by_outdir.items():
        _write_redirect_entries(outdir, entries)

    if output_path_mode == "same":
        print(f"\nDone. Wrote {opt.count * len(input_paths)} files to: {base_outdir.resolve()}")
    else:
        for outdir in output_locations:
            print(f"\nDone. Wrote {opt.count} files to: {outdir}")


__all__ = ["main"]
