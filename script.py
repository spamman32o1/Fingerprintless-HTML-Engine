#!/usr/bin/env python3
"""
HTML fingerprint randomizer (interactive)

- Entity-safe (won't split &nbsp; etc.)
- Chunked span wrapping (less spammy than per-letter)
- Does NOT modify text inside <a>...</a> (anchor text untouched)
- Even smaller per-span position jitter
"""

from __future__ import annotations

import argparse
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

    wrap_chunk_rate: float = 0.027
    chunk_len_min: int = 2
    chunk_len_max: int = 6

    per_word_rate: float = 0.0033

    noise_divs_max: int = 4
    max_nesting: int = 4
    title_prefix: str = "Variant"

    ie_condition_randomize: bool = True
    structure_randomize: bool = True


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
TEMPLATE_SPLIT_RE = re.compile(r"(##.*?##)", re.DOTALL)
TABLE_TAG_RE = re.compile(r"<table([^>]*)>", re.IGNORECASE)
CELLSPACING_ATTR_RE = re.compile(r"\bcellspacing\s*=\s*([\"']?)([^\"'\s>]+)\1", re.IGNORECASE)
STYLE_ATTR_RE = re.compile(r"\bstyle\s*=\s*([\"'])(.*?)\1", re.IGNORECASE | re.DOTALL)
CENTER_TAG_RE = re.compile(r"^<\s*(/?)\s*center\b([^>]*)>$", re.IGNORECASE)

# Skip modifying text inside these tags (includes <a> per your request)
SKIP_TEXT_INSIDE = {"script", "style", "textarea", "code", "pre", "a"}
SAFE_WRAPPER_TAGS = {"div", "section", "span"}
VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}

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


def parse_synonym_lines(lines: List[str]) -> List[List[str]]:
    groups: List[List[str]] = []
    for line in lines:
        parts = [part.strip() for part in line.split("|") if part.strip()]
        if len(parts) >= 2:
            groups.append(parts)
    return groups


def build_synonym_patterns(groups: List[List[str]]) -> List[Tuple[re.Pattern, List[str]]]:
    patterns: List[Tuple[re.Pattern, List[str]]] = []
    for group in groups:
        escaped = sorted((re.escape(word) for word in group), key=len, reverse=True)
        if not escaped:
            continue
        pattern = re.compile(rf"(?i)(?<!\w)(?:{'|'.join(escaped)})(?!\w)")
        patterns.append((pattern, group))
    return patterns


def apply_synonyms(text: str, rng: random.Random, patterns: List[Tuple[re.Pattern, List[str]]]) -> str:
    if not patterns:
        return text

    updated = text
    for pattern, options in patterns:
        updated = pattern.sub(lambda _: pick(rng, options), updated)
    return updated


def normalize_text_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def replace_cellspacing_with_css(html_text: str) -> str:
    def replace_table(match: re.Match[str]) -> str:
        attrs = match.group(1)
        spacing_match = CELLSPACING_ATTR_RE.search(attrs)
        if not spacing_match:
            return match.group(0)

        spacing_value = spacing_match.group(2)
        attrs_clean = CELLSPACING_ATTR_RE.sub("", attrs)
        attrs_clean = re.sub(r"\s{2,}", " ", attrs_clean).strip()

    border_spacing = f"border-spacing:{_css_spacing_value(spacing_value)};"
        style_match = STYLE_ATTR_RE.search(attrs_clean)
        if style_match:
            quote = style_match.group(1)
            style_value = style_match.group(2).strip()
            if style_value and not style_value.rstrip().endswith(";"):
                style_value = f"{style_value};"
            style_value = f"{style_value}{border_spacing}"
            new_style = f'style={quote}{style_value}{quote}'
            attrs_clean = attrs_clean[: style_match.start()] + new_style + attrs_clean[style_match.end() :]
        else:
            attrs_clean = f'{attrs_clean} style="{border_spacing}"'.strip()

        return f"<table{(' ' + attrs_clean) if attrs_clean else ''}>"

    return TABLE_TAG_RE.sub(replace_table, html_text)


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
    base = json.dumps(payload, separators=separators, indent=None)

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


ATTR_RE = re.compile(r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)(\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s\"'>]+))?")
NUMERIC_VALUE_RE = re.compile(r"^\d+(?:\.\d+)?$")


def reorder_tag_attributes(rng: random.Random, tag: str) -> str:
    """Shuffle attributes within a start/self-closing tag while preserving values."""

    if not tag.startswith("<") or tag.startswith("</") or tag.startswith("<!") or tag.startswith("<?"):
        return tag

    m = re.match(r"^<\s*([a-zA-Z0-9:_-]+)([^>]*)>$", tag)
    if not m:
        return tag

    name, rest = m.group(1), m.group(2)
    if not rest.strip():
        return tag

    trailing_slash = rest.rstrip().endswith("/")
    rest = rest.rstrip().rstrip("/")
    attr_text = rest.strip()

    attrs: list[str] = []
    pos = 0
    while pos < len(attr_text):
        while pos < len(attr_text) and attr_text[pos].isspace():
            pos += 1
        if pos >= len(attr_text):
            break

        m_attr = ATTR_RE.match(attr_text, pos)
        if not m_attr:
            return tag

        attrs.append(m_attr.group(0).strip())
        pos = m_attr.end()

    if len(attrs) < 2:
        return tag

    rng.shuffle(attrs)
    attr_str = " ".join(attrs)
    slash = " /" if trailing_slash else ""
    return f"<{name} {attr_str}{slash}>"


def _parse_attr_value(value_text: str | None) -> str | None:
    if not value_text:
        return None

    value = value_text.lstrip()
    if value.startswith("="):
        value = value[1:].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1]
    return value


def _css_spacing_value(raw_value: str | None) -> str:
    value = (raw_value or "0").strip()
    if NUMERIC_VALUE_RE.match(value):
        return f"{value}px"
    return value


def _css_border_value(raw_value: str | None) -> str:
    value = (raw_value or "").strip()
    if not value:
        return ""
    if NUMERIC_VALUE_RE.match(value):
        return f"{value}px solid"
    return value


def _style_has_prop(style_lower: str, prop: str) -> bool:
    return bool(re.search(rf"{re.escape(prop)}\s*:", style_lower))


def _merge_style_value(style_value: str | None, additions: list[tuple[str, str]]) -> str:
    merged_style = style_value or ""
    style_lower = merged_style.lower()
    to_add: list[str] = []
    for prop, value in additions:
        if not value or _style_has_prop(style_lower, prop):
            continue
        to_add.append(f"{prop}:{value};")

    if not to_add:
        return merged_style

    if merged_style and not merged_style.rstrip().endswith(";"):
        merged_style = f"{merged_style};"
    if merged_style:
        merged_style = f"{merged_style} {' '.join(to_add)}"
    else:
        merged_style = " ".join(to_add)
    return merged_style


def _parse_tag_attrs(attr_text: str) -> list[tuple[str, str, str | None]]:
    attrs: list[tuple[str, str, str | None]] = []
    pos = 0
    while pos < len(attr_text):
        while pos < len(attr_text) and attr_text[pos].isspace():
            pos += 1
        if pos >= len(attr_text):
            break

        m_attr = ATTR_RE.match(attr_text, pos)
        if not m_attr:
            return []

        raw = m_attr.group(0).strip()
        attr_name = m_attr.group(1)
        value = _parse_attr_value(m_attr.group(2))
        attrs.append((attr_name, raw, value))
        pos = m_attr.end()
    return attrs


def _normalize_center_tag(tag: str) -> str:
    match = CENTER_TAG_RE.match(tag)
    if not match:
        return tag

    is_close = bool(match.group(1))
    rest = match.group(2)
    if is_close:
        return "</div>"

    trailing_slash = rest.rstrip().endswith("/")
    rest = rest.rstrip().rstrip("/")
    attrs = _parse_tag_attrs(rest.strip())
    if not attrs and rest.strip():
        return tag

    updated_attrs: list[str] = []
    style_value: str | None = None
    for attr_name, raw, value in attrs:
        if attr_name.lower() == "style":
            style_value = value or ""
        else:
            updated_attrs.append(raw)

    merged_style = _merge_style_value(style_value, [("text-align", "center")])
    if merged_style or style_value is not None:
        updated_attrs.append(f'style="{merged_style}"')

    attr_str = " ".join(updated_attrs).strip()
    slash = " /" if trailing_slash else ""
    if attr_str:
        return f"<div {attr_str}{slash}>"
    return f"<div{slash}>"


def _normalize_table_td_attrs(tag: str) -> str:
    if not tag.startswith("<") or tag.startswith("</") or tag.startswith("<!") or tag.startswith("<?"):
        return tag

    m = re.match(r"^<\s*([a-zA-Z0-9:_-]+)([^>]*)>$", tag)
    if not m:
        return tag

    name, rest = m.group(1), m.group(2)
    if name.lower() not in {"table", "td"} or not rest.strip():
        return tag

    trailing_slash = rest.rstrip().endswith("/")
    rest = rest.rstrip().rstrip("/")
    attrs = _parse_tag_attrs(rest.strip())
    if not attrs and rest.strip():
        return tag

    updated_attrs: list[str] = []
    style_value: str | None = None
    additions: list[tuple[str, str]] = []
    align_value: str | None = None

    for attr_name, raw, value in attrs:
        attr_lower = attr_name.lower()
        if attr_lower == "style":
            style_value = value or ""
            continue
        if attr_lower == "border":
            border_value = _css_border_value(value)
            if border_value:
                additions.append(("border", border_value))
            continue
        if attr_lower == "cellpadding":
            additions.append(("padding", _css_spacing_value(value)))
            continue
        if attr_lower == "width":
            additions.append(("width", _css_spacing_value(value)))
            continue
        if attr_lower == "align":
            align_value = (value or "").strip().lower()
            continue
        updated_attrs.append(raw)

    if align_value:
        if name.lower() == "table":
            if align_value == "center":
                additions.append(("margin-left", "auto"))
                additions.append(("margin-right", "auto"))
            elif align_value == "left":
                additions.append(("margin-left", "0"))
                additions.append(("margin-right", "auto"))
            elif align_value == "right":
                additions.append(("margin-left", "auto"))
                additions.append(("margin-right", "0"))
        else:
            additions.append(("text-align", align_value))

    if not additions and style_value is None and len(updated_attrs) == len(attrs):
        return tag

    merged_style = _merge_style_value(style_value, additions)
    if merged_style or style_value is not None or additions:
        updated_attrs.append(f'style="{merged_style}"')

    attr_str = " ".join(updated_attrs).strip()
    slash = " /" if trailing_slash else ""
    if attr_str:
        return f"<{name} {attr_str}{slash}>"
    return f"<{name}{slash}>"


def normalize_table_cellspacing(tag: str) -> str:
    if not tag.startswith("<") or tag.startswith("</") or tag.startswith("<!") or tag.startswith("<?"):
        return tag

    m = re.match(r"^<\s*([a-zA-Z0-9:_-]+)([^>]*)>$", tag)
    if not m:
        return tag

    name, rest = m.group(1), m.group(2)
    if name.lower() != "table" or not rest.strip():
        return tag

    trailing_slash = rest.rstrip().endswith("/")
    rest = rest.rstrip().rstrip("/")
    attr_text = rest.strip()

    attrs: list[tuple[str, str, str | None]] = []
    pos = 0
    while pos < len(attr_text):
        while pos < len(attr_text) and attr_text[pos].isspace():
            pos += 1
        if pos >= len(attr_text):
            break

        m_attr = ATTR_RE.match(attr_text, pos)
        if not m_attr:
            return tag

        raw = m_attr.group(0).strip()
        attr_name = m_attr.group(1)
        value = _parse_attr_value(m_attr.group(2))
        attrs.append((attr_name, raw, value))
        pos = m_attr.end()

    cellspacing_value: str | None = None
    updated_attrs: list[str] = []
    style_value: str | None = None

    for attr_name, raw, value in attrs:
        if attr_name.lower() == "cellspacing":
            cellspacing_value = value
            continue
        if attr_name.lower() == "style":
            style_value = value or ""
            continue
        updated_attrs.append(raw)

    if cellspacing_value is None:
        return tag

    style_lower = (style_value or "").lower()
    additions: list[str] = []
    if "border-spacing" not in style_lower:
        additions.append(f"border-spacing: {_css_spacing_value(cellspacing_value)};")
    if "border-collapse" not in style_lower:
        additions.append("border-collapse: separate;")

    merged_style = style_value or ""
    if additions:
        if merged_style and not merged_style.rstrip().endswith(";"):
            merged_style = f"{merged_style};"
        if merged_style:
            merged_style = f"{merged_style} {' '.join(additions)}"
        else:
            merged_style = " ".join(additions)

    if merged_style or style_value is not None:
        updated_attrs.append(f'style="{merged_style}"')

    attr_str = " ".join(updated_attrs).strip()
    if attr_str:
        slash = " /" if trailing_slash else ""
        return f"<{name} {attr_str}{slash}>"
    slash = " /" if trailing_slash else ""
    return f"<{name}{slash}>"


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

    body_css = " ".join(
        [
            "margin: 0;",
            f"background: {bg_color};",
            f"color: {text_color};",
            f"font-family: {base_font};",
            f"font-size: {font_size}px;",
            f"line-height: {line_height};",
            f"letter-spacing: {letter_spacing}em;",
            f"word-spacing: {word_spacing}em;",
            f"opacity: {opacity};",
        ]
    )

    border_rad = rfloat(rng, 12.0, 20.0, 2)
    border = "1px solid rgba(127,127,127,0.22)" if maybe(rng, 0.35) else "none"
    shadow = "0 6px 18px rgba(0,0,0,0.07)" if maybe(rng, 0.25) else "none"

    layout_mode = pick(rng, ["block", "flow-root", "flex", "grid"])
    gap = rfloat(rng, 6.0, 14.0, 2)
    if layout_mode == "flex":
        extra = " ".join(
            [
                "display:flex;",
                "flex-direction:column;",
                f"gap:{gap}px;",
            ]
        )
    elif layout_mode == "grid":
        extra = " ".join(
            [
                "display:grid;",
                f"gap:{gap}px;",
            ]
        )
    else:
        extra = f"display:{layout_mode};"

    wrapper_css = " ".join(
        [
            f"max-width: {max_w}px;",
            f"padding: {pad}px;",
            f"margin: {margin_top}px auto;",
            f"border-radius: {border_rad}px;",
            f"border: {border};",
            f"box-shadow: {shadow};",
            extra,
            f"transform: rotate({rot}deg) skewX({skew}deg) scale({scale});",
            "transform-origin: top left;",
        ]
    )

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
        structure_randomize=opt.structure_randomize,
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
            "<span></span>",
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
    normalized = normalize_input_html(without_comments)
    return re.sub(r">\s+<", "><", normalized)


def normalize_input_html(html_in: str) -> str:
    parts = TAG_SPLIT_RE.split(html_in)
    out: List[str] = []

    for part in parts:
        if not part:
            continue
        if part.startswith("<") and part.endswith(">"):
            normalized = _normalize_center_tag(part)
            normalized = _normalize_table_td_attrs(normalized)
            out.append(normalized)
        else:
            out.append(part)

    return "".join(out)


def minify_output_html(html_text: str) -> str:
    parts = TAG_SPLIT_RE.split(html_text)
    out: List[str] = []
    tagname_re = re.compile(r"^</?\s*([a-zA-Z0-9:_-]+)")
    skip_stack: List[tuple[str, bool]] = []
    jsonld_type_re = re.compile(r"\btype\s*=\s*(['\"]?)application/ld\+json\1", re.IGNORECASE)

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
                        is_jsonld = name == "script" and bool(jsonld_type_re.search(part))
                        skip_stack.append((name, is_jsonld))
                    elif skip_stack and skip_stack[-1][0] == name:
                        skip_stack.pop()
            continue

        if skip_stack:
            name, is_jsonld = skip_stack[-1]
            if name in ("script", "style"):
                segments = TEMPLATE_SPLIT_RE.split(part)
                for segment in segments:
                    if not segment:
                        continue
                    if TEMPLATE_SPLIT_RE.fullmatch(segment):
                        out.append(segment)
                        continue
                    if name == "script" and is_jsonld:
                        collapsed = re.sub(r"\s+", " ", segment).strip()
                        if collapsed:
                            out.append(collapsed)
                    else:
                        collapsed = re.sub(r"\s+", " ", segment).strip()
                        if collapsed:
                            out.append(collapsed)
            else:
                out.append(part)
            continue

        segments = TEMPLATE_SPLIT_RE.split(part)
        for segment in segments:
            if not segment:
                continue
            if TEMPLATE_SPLIT_RE.fullmatch(segment):
                out.append(segment)
                continue
            collapsed = re.sub(r"\s+", " ", segment)
            if collapsed.strip():
                out.append(collapsed)

    minified = "".join(out)
    minified = re.sub(r">\s+<", "><", minified)
    return minified.strip()


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


@dataclass
class _HtmlNode:
    tag: str | None
    open_tag: str
    close_tag: str | None
    children: list["_HtmlNode"]
    text: str
    self_closing: bool = False

    def render(self) -> str:
        if self.tag is None:
            return self.text
        inner = "".join(child.render() for child in self.children)
        close = "" if self.self_closing else (self.close_tag or "")
        return f"{self.open_tag}{inner}{close}"


def _tag_name(tag_text: str) -> str | None:
    m = re.match(r"^</?\s*([a-zA-Z0-9:_-]+)", tag_text)
    if not m:
        return None
    return m.group(1).lower()


def _is_safe_wrapper(tag_text: str, tag_name: str | None) -> bool:
    if not tag_name or tag_name not in SAFE_WRAPPER_TAGS:
        return False
    m = re.match(r"^<\s*[a-zA-Z0-9:_-]+([^>]*)>$", tag_text)
    if not m:
        return False
    rest = m.group(1)
    return rest.strip() in {"", "/"}


def _parse_html_nodes(html_in: str) -> _HtmlNode:
    parts = TAG_SPLIT_RE.split(html_in)
    root = _HtmlNode(tag="__root__", open_tag="", close_tag="", children=[], text="")
    stack = [root]

    for part in parts:
        if not part:
            continue

        if part.startswith("<") and part.endswith(">"):
            if part.startswith("</"):
                name = _tag_name(part)
                if name and len(stack) > 1 and stack[-1].tag == name:
                    stack[-1].close_tag = part
                    stack.pop()
                else:
                    stack[-1].children.append(_HtmlNode(None, "", None, [], part))
                continue

            if part.startswith("<!") or part.startswith("<?"):
                stack[-1].children.append(_HtmlNode(None, "", None, [], part))
                continue

            name = _tag_name(part)
            if not name:
                stack[-1].children.append(_HtmlNode(None, "", None, [], part))
                continue

            is_self_closing = part.rstrip().endswith("/>") or name in VOID_ELEMENTS
            node = _HtmlNode(tag=name, open_tag=part, close_tag=None, children=[], text="", self_closing=is_self_closing)
            stack[-1].children.append(node)
            if not is_self_closing:
                stack.append(node)
            continue

        stack[-1].children.append(_HtmlNode(None, "", None, [], part))

    return root


def _shuffle_safe_siblings(rng: random.Random, node: _HtmlNode) -> None:
    if node.tag in SKIP_TEXT_INSIDE:
        return

    shuffle_indices = [
        idx
        for idx, child in enumerate(node.children)
        if child.tag is not None and _is_safe_wrapper(child.open_tag, child.tag)
    ]
    if len(shuffle_indices) > 1:
        shuffled = [node.children[idx] for idx in shuffle_indices]
        rng.shuffle(shuffled)
        for idx, child in zip(shuffle_indices, shuffled):
            node.children[idx] = child

    for child in node.children:
        if child.tag is not None:
            _shuffle_safe_siblings(rng, child)


def randomize_structure(rng: random.Random, content_html: str, enabled: bool) -> str:
    if not enabled:
        return content_html

    root = _parse_html_nodes(content_html)
    _shuffle_safe_siblings(rng, root)
    return "".join(child.render() for child in root.children)


def span_wrap_html(
    rng: random.Random,
    html_in: str,
    opt: Opt,
    synonym_patterns: List[Tuple[re.Pattern, List[str]]] | None = None,
) -> str:
    if synonym_patterns is None:
        synonym_patterns = []
    parts = TAG_SPLIT_RE.split(html_in)
    out: List[str] = []

    skip_depth = 0
    skip_tag_stack: List[str] = []
    tagname_re = re.compile(r"^</?\s*([a-zA-Z0-9:_-]+)")

    for part in parts:
        if not part:
            continue

        if part.startswith("<") and part.endswith(">"):
            normalized_tag = normalize_table_cellspacing(part)
            reordered_tag = reorder_tag_attributes(rng, normalized_tag)
            out.append(reordered_tag)
            m = tagname_re.match(reordered_tag)
            if m:
                name = m.group(1).lower()
                is_close = reordered_tag.startswith("</")
                is_self_close = reordered_tag.rstrip().endswith("/>")

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
            if skip_tag_stack and skip_tag_stack[-1] == "a":
                segments = TEMPLATE_SPLIT_RE.split(part)
                for segment in segments:
                    if not segment:
                        continue
                    if TEMPLATE_SPLIT_RE.fullmatch(segment):
                        out.append(segment)
                        continue
                    normalized = normalize_text_whitespace(segment)
                    with_synonyms = apply_synonyms(normalized, rng, synonym_patterns)
                    out.append(wrap_text_node_chunked(rng, with_synonyms, opt))
            else:
                out.append(part)
        else:
            segments = TEMPLATE_SPLIT_RE.split(part)
            for segment in segments:
                if not segment:
                    continue
                if TEMPLATE_SPLIT_RE.fullmatch(segment):
                    out.append(segment)
                    continue
                normalized = normalize_text_whitespace(segment)
                if not normalized.strip():
                    continue
                with_synonyms = apply_synonyms(normalized, rng, synonym_patterns)
                out.append(wrap_text_node_chunked(rng, with_synonyms, opt))

    return "".join(out)


def build_variant(
    rng: random.Random,
    content_html: str,
    opt: Opt,
    idx: int,
    lang: str,
    title: str,
    synonym_patterns: List[Tuple[re.Pattern, List[str]]] | None = None,
) -> str:
    if synonym_patterns is None:
        synonym_patterns = []
    opt = randomize_opt_for_variant(rng, opt)
    content_html = normalize_input_html(content_html)
    content_html = replace_cellspacing_with_css(content_html)
    body_css, wrapper_css = random_css(rng)
    wrapper_class = f"wrap-{uuid.uuid4().hex[:6]}"
    content_class = f"content-{uuid.uuid4().hex[:6]}"
    nested_prefix = f"w{uuid.uuid4().hex[:5]}-"
    structured_html = randomize_structure(rng, content_html, opt.structure_randomize)
    inner = span_wrap_html(rng, structured_html, opt, synonym_patterns)
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
        "style=\"border-collapse:collapse;border-spacing:0;\"><tr><td><![endif]-->"
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
        nested_class = f"{nested_prefix}{d}"
        open_wrap += (
            f'<div class="{nested_class}" '
            f"style=\"padding:{pad}px;margin:{mt}px 0 {mb}px 0;display:{disp};\">"
        )
        close_wrap = "</div>" + close_wrap

    # No template whitespace around inner
    rendered = (
        "<!doctype html>"
        f"<html lang=\"{html.escape(lang, quote=True)}\">"
        "<head>"
        "<meta charset=\"utf-8\" />"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />"
        "<meta name=\"x-apple-disable-message-reformatting\" content=\"yes\" />"
        f"{meta_noise(rng)}"
        f"<title>{html.escape(title)}</title>"
        "<style>"
        f"body{{{body_css}}}"
        f".{wrapper_class}{{{wrapper_css}}}"
        "</style>"
        f"{jsonld_scripts}"
        "</head>"
        "<body>"
        f"{outer_table_open}"
        f"{table_fallback_open}"
        f"<div class=\"{wrapper_class}\">"
        f"{open_wrap}{before}<div class=\"{content_class}\">{inner}</div>{after}{close_wrap}"
        "</div>"
        f"{table_fallback_close}"
        f"{outer_table_close}"
        "</body>"
        "</html>"
    )
    return minify_output_html(rendered)


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


FALLBACK_ENCODINGS = ("latin-1", "windows-1252")


def read_text_with_fallback(path: Path, encoding: str) -> str:
    try:
        return path.read_text(encoding=encoding)
    except UnicodeError as exc:
        for fallback in FALLBACK_ENCODINGS:
            if fallback.lower() == encoding.lower():
                continue
            try:
                print(f"Decode error with '{encoding}'. Retrying with '{fallback}'.")
                return path.read_text(encoding=fallback)
            except UnicodeError:
                continue
        raise SystemExit(
            f"Could not decode '{path}' with '{encoding}' or fallbacks "
            f"{', '.join(FALLBACK_ENCODINGS)}."
        ) from exc


def main() -> None:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--encoding",
        help="Input HTML encoding (default: utf-8; on decode error retries latin-1 then windows-1252).",
    )
    args = parser.parse_args()

    print("=== HTML Fingerprint Randomizer (Skip <a> Text + Smaller Jitter) ===")
    in_path = input("Input HTML file path: ").strip().strip('"').strip("'")
    p = Path(in_path)
    if not p.exists() or not p.is_file():
        raise SystemExit(f"File not found: {p}")

    if args.encoding:
        input_encoding = args.encoding.strip()
    else:
        input_encoding = (
            input(
                "Input encoding (default: utf-8; on decode error retries latin-1 then windows-1252): "
            )
            .strip()
            .lower()
        )
        if not input_encoding:
            input_encoding = "utf-8"

    count = prompt_int("How many variants? ", lo=1)
    seed_in = input("Optional seed (blank = random): ").strip()
    seed = int(seed_in) if seed_in else None

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

    ie_noise_in = (
        input("Add randomized IE conditional comments? (default: yes) [Y/n]: ")
        .strip()
        .lower()
    )
    ie_noise = True if ie_noise_in == "" else ie_noise_in in {"y", "yes", "true", "1"}

    structure_in = (
        input("Randomize safe wrapper structure? (default: yes) [Y/n]: ").strip().lower()
    )
    structure_randomize = (
        True if structure_in == "" else structure_in in {"y", "yes", "true", "1"}
    )

    opt = Opt(
        count=count,
        seed=seed,
        ie_condition_randomize=ie_noise,
        structure_randomize=structure_randomize,
    )
    raw_html = read_text_with_fallback(p, input_encoding)
    sanitized = sanitize_input_html(raw_html)
    content = extract_body_content(sanitized)
    lang = extract_lang(sanitized)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = Path(f"variants_{ts}")
    outdir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(opt.seed)

    for i in range(1, opt.count + 1):
        variant_title = random_title()
        variant = build_variant(rng, content, opt, i, lang, variant_title, synonym_patterns)
        (outdir / f"variant_{i:03d}.html").write_text(variant, encoding="utf-8")

    print(f"\nDone. Wrote {opt.count} files to: {outdir.resolve()}")


if __name__ == "__main__":
    main()
