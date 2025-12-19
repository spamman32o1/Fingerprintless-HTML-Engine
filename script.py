#!/usr/bin/env python3
"""
HTML fingerprint randomizer (interactive)

- Entity-safe (won't split &nbsp; etc.)
- Chunked span wrapping (less spammy than per-letter)
- Does NOT modify text inside <a>...</a> (anchor text untouched)
- Even smaller per-span position jitter
"""

from __future__ import annotations

import html
import random
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Tuple


@dataclass
class Opt:
    count: int
    seed: int | None

    wrap_chunk_rate: float = 0.16
    chunk_len_min: int = 2
    chunk_len_max: int = 6

    per_word_rate: float = 0.02

    noise_divs_max: int = 4
    max_nesting: int = 4
    title_prefix: str = "Variant"


FONT_STACKS = [
    'system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif',
    'system-ui, -apple-system, "Segoe UI Variable", "Segoe UI", Roboto, Arial, sans-serif',
]

TEXT_COLORS = ["#111", "#121212", "#0f0f0f"]
BG_COLORS = ["#fff", "#fefefe", "#fcfcfc"]

ENTITY_RE = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]+|#[0-9]+|#x[0-9A-Fa-f]+);")
TAG_SPLIT_RE = re.compile(r"(<[^>]+>)")
HTML_LANG_RE = re.compile(r"<html[^>]*?\blang\s*=\s*['\"]?([a-zA-Z0-9-]+)", re.IGNORECASE)
BODY_RE = re.compile(r"<body[^>]*>(.*?)</body>", re.IGNORECASE | re.DOTALL)

# Skip modifying text inside these tags (includes <a> per your request)
SKIP_TEXT_INSIDE = {"script", "style", "textarea", "code", "pre", "a"}


def pick(rng: random.Random, xs):
    return xs[rng.randrange(len(xs))]


def rfloat(rng: random.Random, a: float, b: float, digits: int = 3) -> float:
    return round(rng.uniform(a, b), digits)


def rint(rng: random.Random, a: int, b: int) -> int:
    return rng.randint(a, b)


def maybe(rng: random.Random, p: float) -> bool:
    return rng.random() < p


def random_css(rng: random.Random) -> Tuple[str, str]:
    base_font = pick(rng, FONT_STACKS)

    font_size = rfloat(rng, 14.2, 16.0, 2)
    line_height = rfloat(rng, 1.36, 1.60, 3)
    letter_spacing = rfloat(rng, -0.010, 0.028, 4)
    word_spacing = rfloat(rng, -0.015, 0.100, 4)

    max_w = rfloat(rng, 660.0, 900.0, 2)
    pad = rfloat(rng, 10.0, 22.0, 2)
    margin_top = rfloat(rng, 8.0, 18.0, 2)

    rot = rfloat(rng, -0.10, 0.10, 3) if maybe(rng, 0.18) else 0.0
    skew = rfloat(rng, -0.10, 0.10, 3) if maybe(rng, 0.12) else 0.0
    scale = rfloat(rng, 0.9980, 1.0045, 4) if maybe(rng, 0.22) else 1.0

    opacity = rfloat(rng, 0.985, 1.0, 3) if maybe(rng, 0.12) else 1.0
    text_color = pick(rng, TEXT_COLORS)
    bg_color = pick(rng, BG_COLORS)

    body_css = f"""
      margin: 0;
      background: {bg_color};
      color: {text_color};
      font-family: {base_font};
      font-size: {font_size}px;
      line-height: {line_height};
      letter-spacing: {letter_spacing}em;
      word-spacing: {word_spacing}em;
      opacity: {opacity};
    """.strip()

    border_rad = rfloat(rng, 12.0, 20.0, 2)
    border = "1px solid rgba(127,127,127,0.22)" if maybe(rng, 0.35) else "none"
    shadow = "0 6px 18px rgba(0,0,0,0.07)" if maybe(rng, 0.25) else "none"

    layout_mode = pick(rng, ["block", "flow-root", "flex", "grid"])
    gap = rfloat(rng, 6.0, 14.0, 2)
    if layout_mode == "flex":
        extra = f"display:flex; flex-direction:column; gap:{gap}px;"
    elif layout_mode == "grid":
        extra = f"display:grid; gap:{gap}px;"
    else:
        extra = f"display:{layout_mode};"

    wrapper_css = f"""
      max-width: {max_w}px;
      padding: {pad}px;
      margin: {margin_top}px auto;
      border-radius: {border_rad}px;
      border: {border};
      box-shadow: {shadow};
      {extra}
      transform: rotate({rot}deg) skewX({skew}deg) scale({scale});
      transform-origin: top left;
    """.strip()

    return body_css, wrapper_css


def noise_divs(rng: random.Random, nmax: int) -> str:
    n = rint(rng, 0, max(0, nmax))
    bits = []
    for _ in range(n):
        h = rfloat(rng, 0.0, 8.5, 2)
        mt = rfloat(rng, 0.0, 8.5, 2)
        mb = rfloat(rng, 0.0, 8.5, 2)
        w = rfloat(rng, 80.0, 180.0, 2)
        bits.append(
            f'<div aria-hidden="true" style="height:{h}px;margin:{mt}px 0 {mb}px 0;max-width:{w}px;"></div>'
        )
    return "".join(bits)


def letter_style(rng: random.Random) -> str:
    fs = rfloat(rng, 0.998, 1.008, 4)
    ls = rfloat(rng, -0.008, 0.020, 4)
    op = rfloat(rng, 0.970, 1.0, 3) if maybe(rng, 0.14) else 1.0

    # MUCH smaller/rarer position jitter
    dy = rfloat(rng, -0.12, 0.12, 3) if maybe(rng, 0.12) else 0.0

    rot = rfloat(rng, -0.20, 0.20, 3) if maybe(rng, 0.05) else 0.0

    return (
        f"font-size:{fs}em;"
        f"letter-spacing:{ls}em;"
        f"opacity:{op};"
        f"position:relative;top:{dy}px;"
        f"display:inline-block;"
        f"transform:rotate({rot}deg);"
    )


def extract_lang(html_in: str) -> str:
    m = HTML_LANG_RE.search(html_in)
    if m:
        return m.group(1)
    return "en"


def extract_body_content(html_in: str) -> str:
    m = BODY_RE.search(html_in)
    if m:
        return m.group(1)

    stripped = re.sub(r"(?is)<!doctype[^>]*>", "", html_in)
    stripped = re.sub(r"(?is)<head[^>]*>.*?</head>", "", stripped)
    stripped = re.sub(r"(?is)</?html[^>]*>", "", stripped)
    stripped = re.sub(r"(?is)</?body[^>]*>", "", stripped)
    return stripped.strip()


def random_title() -> str:
    return f"letter-{uuid.uuid4().hex[:12]}"


def tokenize_text_preserving_entities(text: str) -> List[tuple[str, str]]:
    tokens: List[tuple[str, str]] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i].isspace():
            j = i + 1
            while j < n and text[j].isspace():
                j += 1
            tokens.append(("ws", text[i:j]))
            i = j
            continue

        m = ENTITY_RE.match(text, i)
        if m:
            tokens.append(("entity", m.group(0)))
            i = m.end()
            continue

        tokens.append(("char", text[i]))
        i += 1

    return tokens


def wrap_text_node_chunked(rng: random.Random, text: str, opt: Opt) -> str:
    if not text or not text.strip():
        return text

    if maybe(rng, opt.per_word_rate):
        chunks = re.split(r"(\s+)", text)
        out: List[str] = []
        for ch in chunks:
            if not ch or ch.isspace():
                out.append(ch)
                continue
            toks = tokenize_text_preserving_entities(ch)
            rendered = []
            for kind, val in toks:
                if kind == "ws":
                    rendered.append(val)
                elif kind == "entity":
                    rendered.append(val)
                else:
                    rendered.append(html.escape(val, quote=False))
            chunk_out = "".join(rendered)
            if maybe(rng, 0.28):
                out.append(f'<span style="{letter_style(rng)}">{chunk_out}</span>')
            else:
                out.append(chunk_out)
        return "".join(out)

    toks = tokenize_text_preserving_entities(text)
    out: List[str] = []
    i = 0

    while i < len(toks):
        kind, val = toks[i]

        if kind == "ws":
            out.append(val)
            i += 1
            continue

        if kind == "entity":
            if maybe(rng, opt.wrap_chunk_rate * 0.30):
                out.append(f'<span style="{letter_style(rng)}">{val}</span>')
            else:
                out.append(val)
            i += 1
            continue

        # char
        c = val
        is_punct = bool(re.match(r"[\.\,\!\?\:\;\-\—\(\)\[\]\{\}\'\"]", c))
        start_p = opt.wrap_chunk_rate * (0.35 if is_punct else 1.0)

        if maybe(rng, start_p):
            L = rint(rng, opt.chunk_len_min, opt.chunk_len_max)
            chunk = []
            j = i
            while j < len(toks) and len(chunk) < L:
                k, v = toks[j]
                if k in ("ws", "entity"):
                    break
                chunk.append(html.escape(v, quote=False))
                j += 1
            if chunk:
                out.append(f'<span style="{letter_style(rng)}">{"".join(chunk)}</span>')
                i = j
                continue

        out.append(html.escape(c, quote=False))
        i += 1

    return "".join(out)


def span_wrap_html(rng: random.Random, html_in: str, opt: Opt) -> str:
    parts = TAG_SPLIT_RE.split(html_in)
    out: List[str] = []

    skip_depth = 0
    skip_tag_stack: List[str] = []
    tagname_re = re.compile(r"^</?\s*([a-zA-Z0-9:_-]+)")

    for part in parts:
        if not part:
            continue

        if part.startswith("<") and part.endswith(">"):
            out.append(part)
            m = tagname_re.match(part)
            if m:
                name = m.group(1).lower()
                is_close = part.startswith("</")
                is_self_close = part.rstrip().endswith("/>")

                if name in SKIP_TEXT_INSIDE and not is_self_close:
                    if not is_close:
                        skip_depth += 1
                        skip_tag_stack.append(name)
                    else:
                        if skip_tag_stack and skip_tag_stack[-1] == name:
                            skip_tag_stack.pop()
                            skip_depth = max(0, skip_depth - 1)
            continue

        # text node
        if skip_depth > 0:
            out.append(part)
        else:
            out.append(wrap_text_node_chunked(rng, part, opt))

    return "".join(out)


def build_variant(
    rng: random.Random, content_html: str, opt: Opt, idx: int, lang: str, title: str
) -> str:
    body_css, wrapper_css = random_css(rng)
    inner = span_wrap_html(rng, content_html, opt)

    before = noise_divs(rng, opt.noise_divs_max)
    after = noise_divs(rng, opt.noise_divs_max)

    depth = rint(rng, 1, max(1, opt.max_nesting))
    open_wrap = ""
    close_wrap = ""
    for d in range(depth):
        pad = rfloat(rng, 0.0, 12.0, 2)
        mt = rfloat(rng, 0.0, 10.0, 2)
        mb = rfloat(rng, 0.0, 10.0, 2)
        disp = pick(rng, ["block", "flow-root", "contents"])
        open_wrap += f'<div class="w{d}" style="padding:{pad}px;margin:{mt}px 0 {mb}px 0;display:{disp};">'
        close_wrap = "</div>" + close_wrap

    # No template whitespace around inner
    return (
        "<!doctype html>"
        f"<html lang=\"{html.escape(lang, quote=True)}\">"
        "<head>"
        "<meta charset=\"utf-8\" />"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />"
        f"<title>{html.escape(title)}</title>"
        "<style>"
        f"body{{{body_css}}}"
        f".wrap{{{wrapper_css}}}"
        "</style>"
        "</head>"
        "<body>"
        "<div class=\"wrap\">"
        f"{open_wrap}{before}<div class=\"content\">{inner}</div>{after}{close_wrap}"
        "</div>"
        "</body>"
        "</html>"
    )


def prompt_int(msg: str, lo: int = 1) -> int:
    while True:
        s = input(msg).strip()
        try:
            n = int(s)
        except ValueError:
            print("Please enter an integer.")
            continue
        if n < lo:
            print(f"Must be >= {lo}.")
            continue
        return n


def main() -> None:
    print("=== HTML Fingerprint Randomizer (Skip <a> Text + Smaller Jitter) ===")
    in_path = input("Input HTML file path: ").strip().strip('"').strip("'")
    p = Path(in_path)
    if not p.exists() or not p.is_file():
        raise SystemExit(f"File not found: {p}")

    count = prompt_int("How many variants? ", lo=1)
    seed_in = input("Optional seed (blank = random): ").strip()
    seed = int(seed_in) if seed_in else None

    opt = Opt(count=count, seed=seed)
    raw_html = p.read_text(encoding="utf-8")
    content = extract_body_content(raw_html)
    lang = extract_lang(raw_html)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = Path(f"variants_{ts}")
    outdir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(opt.seed)

    for i in range(1, opt.count + 1):
        variant_title = random_title()
        variant = build_variant(rng, content, opt, i, lang, variant_title)
        (outdir / f"variant_{i:03d}.html").write_text(variant, encoding="utf-8")

    print(f"\nDone. Wrote {opt.count} files to: {outdir.resolve()}")


if __name__ == "__main__":
    main()