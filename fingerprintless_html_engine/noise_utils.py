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
    ("description", ["Document shell", "Layout wrapper", "Content frame", "Minimal placeholder"]),
    ("theme-color", ["#f8f8f8", "#ffffff", "#111111", "#f3f3f3"]),
    ("referrer", ["no-referrer", "origin", "same-origin", "strict-origin-when-cross-origin"]),
    ("robots", ["index, follow", "noindex, nofollow", "noarchive", "nosnippet"]),
    ("color-scheme", ["light dark", "only light", "light", "dark"]),
    (
        "viewport",
        [
            "width=device-width, initial-scale=1",
            "width=device-width,initial-scale=1,viewport-fit=cover",
            "initial-scale=1.0, width=device-width",
            "width=device-width, initial-scale=1, maximum-scale=1",
        ],
    ),
    ("rating", ["General", "Safe", "Clean"]),
    ("distribution", ["Global", "Worldwide", "Public"]),
    ("format-detection", ["telephone=no", "date=no", "email=no"]),
    ("profile:label", ["content-shell", "doc-frame", "layout-pass"]),
    ("data-origin", ["capture", "archive", "render", "variant"]),
    ("data-layout-step", ["draft", "pass", "final", "stable"]),
]

HTTP_EQUIV_NOISE_CANDIDATES = [
    ("content-language", ["en", "en-US", "en-GB", "fr", "de"]),
    ("cache-control", ["no-cache", "max-age=0", "no-store"]),
    ("pragma", ["no-cache"]),
    ("expires", ["0", "Mon, 01 Jan 1990 00:00:00 GMT"]),
    ("x-ua-compatible", ["IE=edge"]),
    ("x-dns-prefetch-control", ["on", "off"]),
    ("default-style", ["base", "clean", "main"]),
    ("content-type", ["text/html; charset=utf-8", "text/html; charset=iso-8859-1"]),
    ("refresh", ["30", "120"]),
]

PROPERTY_NOISE_CANDIDATES = [
    ("og:type", ["document", "article", "page", "website"]),
    ("og:locale", ["en_US", "en_GB", "fr_FR", "de_DE"]),
    ("og:section", ["layout", "content", "shell", "frame"]),
    ("og:site_name", ["Document Shell", "Layout Frame", "Content Panel"]),
    ("social:card", ["summary", "summary_large", "compact"]),
    ("social:title", ["Document shell", "Layout wrapper", "Content frame"]),
    ("social:description", ["Minimal placeholder", "Layout shell", "Content summary"]),
]


def _randomize_case(rng: random.Random, text: str) -> str:
    if maybe(rng, 0.12):
        return text.upper()
    if maybe(rng, 0.12):
        return text.lower()
    if maybe(rng, 0.08):
        return text.title()
    if maybe(rng, 0.10):
        return "".join(ch.upper() if maybe(rng, 0.5) else ch.lower() for ch in text)
    return text


def _format_meta_content(rng: random.Random, content: str) -> str:
    value = content
    tokens = value.replace(",", " ").replace(";", " ").split()
    if len(tokens) > 1 and maybe(rng, 0.35):
        sep = pick(rng, [", ", ",", "; ", ";"])
        value = sep.join(tokens)
    if maybe(rng, 0.18):
        value = value.replace("=", " = ")
    if maybe(rng, 0.20):
        value = value.replace(",", " , ").replace(";", " ; ")
        value = " ".join(value.split())
    value = _randomize_case(rng, value)
    if maybe(rng, 0.20):
        value = f" {value}"
    if maybe(rng, 0.20):
        value = f"{value} "
    return value


def meta_noise(rng: random.Random) -> str:
    n = rint(rng, 2, 6)
    tags: list[str] = []
    seen_names: set[tuple[str, str]] = set()

    for _ in range(n):
        use_property = maybe(rng, 0.22)
        use_http_equiv = not use_property and maybe(rng, 0.18)
        if use_property:
            attr_name = "property"
            name, values = pick(rng, PROPERTY_NOISE_CANDIDATES)
        elif use_http_equiv:
            attr_name = "http-equiv"
            name, values = pick(rng, HTTP_EQUIV_NOISE_CANDIDATES)
        else:
            attr_name = "name"
            name, values = pick(rng, META_NOISE_CANDIDATES)
        name_key = (attr_name, name)
        if name_key in seen_names and maybe(rng, 0.55):
            continue
        content = pick(rng, values)
        if maybe(rng, 0.30):
            content = f"{content}-{uuid.uuid4().hex[:6]}"
        if attr_name == "name" and maybe(rng, 0.20):
            name = f"x-{name}" if not name.startswith("x-") else name
        if maybe(rng, 0.12):
            name = _randomize_case(rng, name)
        content = _format_meta_content(rng, content)
        tags.append(
            f'<meta {attr_name}="{html.escape(name, quote=True)}" content="{html.escape(content, quote=True)}" />'
        )
        seen_names.add(name_key)

    return "".join(tags)
