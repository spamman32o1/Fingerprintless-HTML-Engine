from __future__ import annotations

import html
import random
import uuid

from .random_utils import maybe, pick, rfloat, rint


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
            '<meta http-equiv="X-UA-Compatible" content="IE=edge">',
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
    ("description", ["Layout summary", "Document overview", "Content frame", "Minimal document stub"]),
    ("rating", ["General", "Safe", "Clean"]),
    ("distribution", ["Global", "Worldwide", "Public"]),
    ("format-detection", ["telephone=no", "date=no", "email=no"]),
    ("theme-color", ["#111111", "#0f0f0f", "#fefefe", "#fcfcfc"]),
    (
        "referrer",
        [
            "no-referrer",
            "same-origin",
            "origin",
            "strict-origin",
            "strict-origin-when-cross-origin",
        ],
    ),
    ("robots", ["noindex", "nofollow", "noarchive", "index,follow"]),
    ("color-scheme", ["light", "dark", "light dark"]),
    (
        "viewport",
        [
            "width=device-width, initial-scale=1",
            "width=device-width, initial-scale=1.0, maximum-scale=1.0",
            "width=device-width, height=device-height, initial-scale=1",
            "width=device-width, initial-scale=1, viewport-fit=cover",
        ],
    ),
    ("profile:label", ["content-shell", "doc-frame", "layout-pass"]),
    ("data-origin", ["capture", "archive", "render", "variant"]),
    ("data-layout-step", ["draft", "pass", "final", "stable"]),
]

HTTP_EQUIV_NOISE_CANDIDATES = [
    ("content-type", ["text/html; charset=utf-8", "text/html; charset=iso-8859-1"]),
    ("content-language", ["en", "en-US", "en-GB"]),
    ("content-style-type", ["text/css"]),
    ("content-script-type", ["text/javascript"]),
    ("x-ua-compatible", ["IE=edge", "IE=Edge"]),
    ("cache-control", ["no-cache", "max-age=0", "no-store"]),
]

PROPERTY_NOISE_CANDIDATES = [
    ("og:title", ["Document frame", "Markup layout", "Reader shell", "Content panel"]),
    ("og:description", ["Layout summary", "Minimal document stub", "Content wrapper"]),
    ("og:type", ["article", "website", "document"]),
    ("og:locale", ["en_US", "en_GB"]),
    ("card:title", ["Document frame", "Layout draft", "Content shell"]),
    ("card:description", ["Layout summary", "Content frame", "Document overview"]),
]


def _randomize_case(rng: random.Random, text: str) -> str:
    if maybe(rng, 0.35):
        return text.upper()
    if maybe(rng, 0.35):
        return text.lower()

    chars = []
    for ch in text:
        if ch.isalpha() and maybe(rng, 0.5):
            chars.append(ch.upper())
        elif ch.isalpha():
            chars.append(ch.lower())
        else:
            chars.append(ch)
    return "".join(chars)


def _add_separator_whitespace(rng: random.Random, text: str) -> str:
    seps = {",", ";", "=", ":"}
    bits: list[str] = []
    for ch in text:
        if ch in seps and maybe(rng, 0.5):
            left = " " if maybe(rng, 0.4) else ""
            right = " " if maybe(rng, 0.4) else ""
            bits.append(f"{left}{ch}{right}")
        else:
            bits.append(ch)
    return "".join(bits)


def _format_meta_content(rng: random.Random, content: str, values: list[str]) -> str:
    parts = [content]
    if maybe(rng, 0.30):
        extra_count = rint(rng, 1, 2)
        for _ in range(extra_count):
            parts.append(pick(rng, values))

    if len(parts) > 1:
        separator = pick(rng, [",", ";"])
        content = separator.join(parts)

    if "," in content and maybe(rng, 0.25):
        content = content.replace(",", ";")

    content = _add_separator_whitespace(rng, content)

    if maybe(rng, 0.30):
        content = _randomize_case(rng, content)

    if maybe(rng, 0.20):
        content = f" {content}"
    if maybe(rng, 0.20):
        content = f"{content} "

    return content


def meta_noise(rng: random.Random) -> str:
    n = rint(rng, 2, 6)
    tags: list[str] = []
    seen_names: set[str] = set()
    seen_properties: set[str] = set()
    seen_http_equiv: set[str] = set()

    for _ in range(n):
        roll = rng.random()
        if roll < 0.18:
            prop, values = pick(rng, PROPERTY_NOISE_CANDIDATES)
            if prop in seen_properties and maybe(rng, 0.55):
                continue
            content = _format_meta_content(rng, pick(rng, values), values)
            if maybe(rng, 0.25):
                prop = prop.upper() if maybe(rng, 0.5) else prop.lower()
            tags.append(
                f'<meta property="{html.escape(prop, quote=True)}" content="{html.escape(content, quote=True)}" />'
            )
            seen_properties.add(prop)
            continue

        if roll < 0.36:
            http_equiv, values = pick(rng, HTTP_EQUIV_NOISE_CANDIDATES)
            if http_equiv in seen_http_equiv and maybe(rng, 0.55):
                continue
            content = _format_meta_content(rng, pick(rng, values), values)
            if maybe(rng, 0.15):
                http_equiv = http_equiv.upper()
            tags.append(
                f'<meta http-equiv="{html.escape(http_equiv, quote=True)}" content="{html.escape(content, quote=True)}" />'
            )
            seen_http_equiv.add(http_equiv)
            continue

        name, values = pick(rng, META_NOISE_CANDIDATES)
        if name in seen_names and maybe(rng, 0.55):
            continue
        content = _format_meta_content(rng, pick(rng, values), values)
        if maybe(rng, 0.30):
            content = f"{content}-{uuid.uuid4().hex[:6]}"
        if maybe(rng, 0.20):
            name = f"x-{name}" if not name.startswith("x-") else name
        if maybe(rng, 0.12):
            name = name.upper()
        tags.append(f'<meta name="{html.escape(name, quote=True)}" content="{html.escape(content, quote=True)}" />')
        seen_names.add(name)

    return "".join(tags)
