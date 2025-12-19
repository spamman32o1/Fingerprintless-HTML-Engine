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
import json
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

    wrap_chunk_rate: float = 0.08
    chunk_len_min: int = 2
    chunk_len_max: int = 6

    per_word_rate: float = 0.01

    noise_divs_max: int = 4
    max_nesting: int = 4
    title_prefix: str = "Variant"

    ie_condition_randomize: bool = True


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

JSONLD_MUTATION_POOL = [
    {},
    {"@context": ""},
    {"@context": None},
    [],
    [{}],
    {"x": 1},
    {"seed": "a9"},
]

FORBIDDEN_BRAND_RE = re.compile(
    r"\b(google|amazon|apple|microsoft|samsung|sony|nike|adidas|coca[- ]?cola|pepsi|tesla)\b",
    re.IGNORECASE,
)


def pick(rng: random.Random, xs):
    return xs[rng.randrange(len(xs))]


def _normalized_json_order(rng: random.Random, val):
    if isinstance(val, dict):
        items = list(val.items())
        rng.shuffle(items)
        return {k: _normalized_json_order(rng, v) for k, v in items}
    if isinstance(val, list):
        return [_normalized_json_order(rng, v) for v in val]
    return val


FORBIDDEN_URL_RE = re.compile(r"https?://[^\s\"'>]+", re.IGNORECASE)


def _violates_jsonld_guardrails(payload_text: str) -> bool:
    lower = payload_text.lower()
    if "@type" in lower or "schema.org" in lower:
        return True

    if FORBIDDEN_BRAND_RE.search(payload_text):
        return True

    for url in FORBIDDEN_URL_RE.findall(payload_text):
        if not url.endswith(".invalid"):
            return True

    return False


def _serialize_jsonld_payload(rng: random.Random, payload) -> str:
    separators = pick(rng, [(",", ":"), (",", ": "), (", ", ":"), (", ", ": ")])
    indent_choice = pick(rng, [None, 0, 1, 2, 3])
    indent = None if indent_choice in (None, 0) else indent_choice

    base = json.dumps(payload, separators=separators, indent=indent)

    if maybe(rng, 0.35):
        base = f"\n{base}\n"

    pad_left = " " * rint(rng, 0, 2)
    pad_right = " " * rint(rng, 0, 2)
    return f"{pad_left}{base}{pad_right}"


def build_fake_jsonld_scripts(rng: random.Random) -> str:
    n_scripts = rint(rng, 0, 2)
    blocks: list[str] = []

    for _ in range(n_scripts):
        for _ in range(5):
            payload = rng.choice(JSONLD_MUTATION_POOL)
            payload_copy = json.loads(json.dumps(payload))
            normalized = _normalized_json_order(rng, payload_copy)
            json_text = _serialize_jsonld_payload(rng, normalized)

            if len(json_text.encode("utf-8")) > 200:
                continue

            if _violates_jsonld_guardrails(json_text):
                continue

            try:
                json.loads(json_text)
            except json.JSONDecodeError:
                continue

            blocks.append(f'<script type="application/ld+json">{json_text}</script>')
            break

    return "".join(blocks)


def _clamp_rate(val: float) -> float:
    return max(0.0, min(1.0, val))


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


def randomize_opt_for_variant(rng: random.Random, opt: Opt) -> Opt:
    wrap_factor = rfloat(rng, 0.8, 1.2)
    word_factor = rfloat(rng, 0.8, 1.2)

    chunk_len_min = max(1, opt.chunk_len_min + rint(rng, -1, 1))
    chunk_len_max = max(chunk_len_min, opt.chunk_len_max + rint(rng, -1, 1))

    noise_divs_max = max(0, opt.noise_divs_max + rint(rng, -1, 1))

    return Opt(
        count=opt.count,
        seed=opt.seed,
        wrap_chunk_rate=_clamp_rate(opt.wrap_chunk_rate * wrap_factor),
        chunk_len_min=chunk_len_min,
        chunk_len_max=chunk_len_max,
        per_word_rate=_clamp_rate(opt.per_word_rate * word_factor),
        noise_divs_max=noise_divs_max,
        max_nesting=opt.max_nesting,
        title_prefix=opt.title_prefix,
        ie_condition_randomize=opt.ie_condition_randomize,
    )


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


def random_ie_conditional_comment(rng: random.Random) -> str:
    conditions = [
        "IE",
        "(IE)",
        "!false",
        "!(false)",
        "IE & !false",
    ]
    cond = pick(rng, conditions)

    # Allow capitalization/whitespace noise in the condition tokens
    cond = cond.upper() if maybe(rng, 0.20) else cond
    cond = cond.lower() if maybe(rng, 0.20) else cond

    if maybe(rng, 0.35):
        cond = f" {cond}"
    if maybe(rng, 0.35):
        cond = f"{cond} "

    if_kw = "IF" if maybe(rng, 0.30) else "if"
    endif_kw = "ENDIF" if maybe(rng, 0.30) else "endif"

    open_pad = " " if maybe(rng, 0.30) else ""
    close_pad = " " if maybe(rng, 0.30) else ""
    bracket_ws = " " if maybe(rng, 0.40) else ""

    opening = f"<!--{open_pad}[{if_kw}{bracket_ws}{cond}{bracket_ws}]>"
    closing = f"<![{endif_kw}{close_pad}]-->"

    payload = pick(
        rng,
        [
            "",
            " ",
            "<!--noop-->",
            "<meta http-equiv=\"X-UA-Compatible\" content=\"IE=edge\">",
        ],
    )
    return f"{opening}{payload}{closing}"


def ie_noise_block(rng: random.Random, enabled: bool) -> str:
    if not enabled:
        return ""

    n_blocks = rint(rng, 1, 3)
    bits = []
    for _ in range(n_blocks):
        if maybe(rng, 0.65):
            bits.append(random_ie_conditional_comment(rng))
    return "".join(bits)


META_NOISE_CANDIDATES = [
    ("application-name", ["Reader", "Letterbox", "HTML Shell", "DocFrame"]),
    ("generator", ["fp-less-engine", "static-maker", "markup-crafter"]),
    ("author", ["layout", "markup", "builder", "compose"]),
    ("keywords", ["letters", "content", "layout", "wrapper", "document"]),
    ("rating", ["General", "Safe", "Clean"]),
    ("distribution", ["Global", "Worldwide", "Public"]),
    ("format-detection", ["telephone=no", "date=no", "email=no"]),
    ("profile:label", ["content-shell", "doc-frame", "layout-pass"]),
    ("data-origin", ["capture", "archive", "render", "variant"]),
    ("data-layout-step", ["draft", "pass", "final", "stable"]),
]


def meta_noise(rng: random.Random) -> str:
    n = rint(rng, 2, 6)
    tags: list[str] = []
    seen_names: set[str] = set()

    for _ in range(n):
        name, values = pick(rng, META_NOISE_CANDIDATES)
        if name in seen_names and maybe(rng, 0.55):
            continue
        content = pick(rng, values)
        if maybe(rng, 0.30):
            content = f"{content}-{uuid.uuid4().hex[:6]}"
        if maybe(rng, 0.20):
            name = f"x-{name}" if not name.startswith("x-") else name
        if maybe(rng, 0.12):
            name = name.upper()
        tags.append(f'<meta name="{html.escape(name, quote=True)}" content="{html.escape(content, quote=True)}" />')
        seen_names.add(name)

    return "".join(tags)


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


def sanitize_input_html(html_in: str) -> str:
    """Remove HTML comments and collapse inter-tag whitespace.

    Comments are stripped using a DOTALL pattern to cover multiline blocks, and
    whitespace between tags (e.g., newlines/indentation) is collapsed from
    ">\s+<" to "><" to avoid introducing visible gaps while leaving inline
    text unchanged.
    """

    without_comments = re.sub(r"<!--.*?-->", "", html_in, flags=re.DOTALL)
    return re.sub(r">\s+<", "><", without_comments)


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
    opt = randomize_opt_for_variant(rng, opt)
    body_css, wrapper_css = random_css(rng)
    inner = span_wrap_html(rng, content_html, opt)
    jsonld_scripts = build_fake_jsonld_scripts(rng)

    ie_before = ie_noise_block(rng, opt.ie_condition_randomize)
    ie_after = ie_noise_block(rng, opt.ie_condition_randomize)

    before = ie_before + noise_divs(rng, opt.noise_divs_max)
    after = noise_divs(rng, opt.noise_divs_max) + ie_after

    outer_table_open = (
        '<table role="presentation" class="layout-table" '
        "style=\"width:100%;border-collapse:collapse;border-spacing:0;\">"
        "<tr><td>"
    )
    outer_table_close = "</td></tr></table>"

    table_fallback_open = (
        "<!--[if (mso)|(IE)]><table role=\"presentation\" width=\"100%\" "
        "style=\"border-collapse:collapse;border-spacing:0;\"><tr><td><![endif]>"
    )
    table_fallback_close = "<!--[if (mso)|(IE)]></td></tr></table><![endif]-->"

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
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />"
        "<meta name=\"x-apple-disable-message-reformatting\" />"
        f"{meta_noise(rng)}"
        f"<title>{html.escape(title)}</title>"
        "<style>"
        f"body{{{body_css}}}"
        f".wrap{{{wrapper_css}}}"
        "</style>"
        f"{jsonld_scripts}"
        "</head>"
        "<body>"
        f"{outer_table_open}"
        f"{table_fallback_open}"
        "<div class=\"wrap\">"
        f"{open_wrap}{before}<div class=\"content\">{inner}</div>{after}{close_wrap}"
        "</div>"
        f"{table_fallback_close}"
        f"{outer_table_close}"
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

    ie_noise_in = (
        input("Add randomized IE conditional comments? (default: yes) [Y/n]: ")
        .strip()
        .lower()
    )
    ie_noise = True if ie_noise_in == "" else ie_noise_in in {"y", "yes", "true", "1"}

    opt = Opt(count=count, seed=seed, ie_condition_randomize=ie_noise)
    raw_html = p.read_text(encoding="utf-8")
    sanitized = sanitize_input_html(raw_html)
    content = extract_body_content(sanitized)
    lang = extract_lang(sanitized)

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
