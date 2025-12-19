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
    ("generator", ["fp-less-engine", "static-maker", "markup-crafter", "scribe-bundle"]),
    ("author", ["layout", "markup", "builder", "compose", "assembler"]),
    (
        "application-category",
        ["productivity", "utilities", "documentation", "offline-viewer", "notes"],
    ),
    ("keywords", ["letters", "content", "layout", "wrapper", "document", "reader"]),
    (
        "description",
        ["Document shell", "Layout wrapper", "Content frame", "Minimal placeholder", "Reader scaffold"],
    ),
    ("theme-color", ["#f8f8f8", "#ffffff", "#111111", "#f3f3f3", "#0f172a"]),
    (
        "referrer",
        [
            "no-referrer",
            "origin",
            "same-origin",
            "strict-origin-when-cross-origin",
            "origin-when-cross-origin",
            "no-referrer-when-downgrade",
        ],
    ),
    ("robots", ["index, follow", "noindex, nofollow", "noarchive", "nosnippet", "index, nofollow"]),
    ("color-scheme", ["light dark", "only light", "light", "dark"]),
    (
        "viewport",
        [
            "width=device-width, initial-scale=1",
            "width=device-width,initial-scale=1,viewport-fit=cover",
            "initial-scale=1.0, width=device-width",
            "width=device-width, initial-scale=1, maximum-scale=1",
            "minimum-scale=1, width=device-width",
        ],
    ),
    ("rating", ["General", "Safe", "Clean", "Everyone"]),
    ("distribution", ["Global", "Worldwide", "Public", "Internal"]),
    ("format-detection", ["telephone=no", "date=no", "email=no"]),
    ("profile:label", ["content-shell", "doc-frame", "layout-pass", "shell-step"]),
    (
        "data-origin",
        [
            "capture",
            "archive",
            "render",
            "variant",
            "trace-" + uuid.uuid4().hex[:4],
        ],
    ),
    (
        "data-layout-step",
        [
            "draft",
            "pass",
            "final",
            "stable",
            "pass_" + uuid.uuid4().hex[:3],
        ],
    ),
    (
        "apple-mobile-web-app-title",
        ["DocShell", "ReaderFrame", "Shell-View", "Frame_Viewer", "ShellPlay"],
    ),
    (
        "apple-mobile-web-app-capable",
        ["yes", "no", "YES", "minimal-ui"],
    ),
    (
        "apple-mobile-web-app-status-bar-style",
        ["default", "black", "black-translucent", "light-content"],
    ),
    (
        "msapplication-TileColor",
        ["#2b5797", "#0b3d91", "#111827", "#f3f4f6"],
    ),
    (
        "msapplication-config",
        ["/browserconfig.xml", "none", "about:blank"],
    ),
    ("msapplication-navbutton-color", ["#111111", "#ffffff", "#4b5563"]),
    ("application-name-variant", ["Reader Lite", "Doc Shell Alt", "Frame View"]),
    ("apple-touch-fullscreen", ["yes", "no"]),
    ("mobileoptimized", ["320", "375", "414"]),
    ("handheldfriendly", ["true", "yes"]),
    ("google-site-verification", [uuid.uuid4().hex[:20], uuid.uuid4().hex[:24]]),
    ("msvalidate.01", [uuid.uuid4().hex[:20], uuid.uuid4().hex[:24]]),
    ("yandex-verification", [uuid.uuid4().hex[:20], uuid.uuid4().hex[:24]]),
    ("facebook-domain-verification", [uuid.uuid4().hex[:20], uuid.uuid4().hex[:24]]),
    (
        "apple-itunes-app",
        [
            "app-id=123456789, affiliate-data=partner123",
            "app-id=789654321",
            "app-id=567890123, app-argument=fp-less://shell",
        ],
    ),
    (
        "manifest",
        ["/manifest.json", "./static/manifest.webmanifest", "manifest.webmanifest"],
    ),
    ("application-version", ["1.0", "1.2.3", "2024.04", "0.9.0-beta"]),
    ("build-id", [uuid.uuid4().hex[:8], uuid.uuid4().hex[:10]]),
    (
        "prefers-color-scheme",
        ["dark", "light", "light dark"],
    ),
    (
        "twitter:site",
        ["@shell_app", "@DocFrame", "@LayoutViewer", "@frame_app"],
    ),
    (
        "twitter:title",
        ["Doc Shell", "Content Wrapper", "Frame_View", "Layout-Panel"],
    ),
    (
        "twitter:description",
        [
            "document shell preview",
            "layout frame - v1",
            "content-wrapper_" + uuid.uuid4().hex[:5],
            "frame builder beta",
        ],
    ),
]

HTTP_EQUIV_NOISE_CANDIDATES = [
    ("content-language", ["en", "en-US", "en-GB", "fr", "de", "es"]),
    (
        "cache-control",
        [
            "no-cache",
            "max-age=0",
            "no-store",
            "max-age=300, must-revalidate",
            "private, max-age=60, stale-while-revalidate=30",
        ],
    ),
    ("pragma", ["no-cache", "public"]),
    ("expires", ["0", "Mon, 01 Jan 1990 00:00:00 GMT", "-1"]),
    ("x-ua-compatible", ["IE=edge", "IE=11"]),
    ("x-dns-prefetch-control", ["on", "off"]),
    ("default-style", ["base", "clean", "main", "reader"]),
    ("content-type", ["text/html; charset=utf-8", "text/html; charset=iso-8859-1"]),
    ("refresh", ["30", "120", "600; url=/" + uuid.uuid4().hex[:4]]),
    (
        "referrer",
        [
            "strict-origin",
            "same-origin",
            "origin-when-cross-origin",
            "no-referrer",
        ],
    ),
    ("x-content-type-options", ["nosniff", "NoSniff"]),
    ("imagetoolbar", ["no", "yes"]),
]

PROPERTY_NOISE_CANDIDATES = [
    ("og:type", ["document", "article", "page", "website", "profile"]),
    ("og:locale", ["en_US", "en_GB", "fr_FR", "de_DE", "es_ES"]),
    ("og:section", ["layout", "content", "shell", "frame", "wrapper"]),
    ("og:site_name", ["Document Shell", "Layout Frame", "Content Panel", "Shell Stack"]),
    (
        "og:title",
        ["Doc Shell", "Content Wrapper", "Frame_View", "Layout-Panel", "Reader Shell"],
    ),
    (
        "og:description",
        [
            "Minimal placeholder",
            "Layout shell",
            "Content summary",
            "frame detail " + uuid.uuid4().hex[:4],
            "document wrapper preview",
        ],
    ),
    ("og:url", ["https://example.com/" + uuid.uuid4().hex[:6], "/docs", "/viewer"]),
    (
        "og:image",
        [
            "https://example.com/img/share.png",
            "https://cdn.example.com/" + uuid.uuid4().hex[:6] + "/card.jpg",
            "https://assets.example.com/cover.png",
        ],
    ),
    ("og:image:alt", ["Document shell preview", "Layout preview", "Content card"]),
    ("og:determiner", ["the", "a", "an"]),
    ("social:card", ["summary", "summary_large", "compact", "image"]),
    ("social:title", ["Document shell", "Layout wrapper", "Content frame", "Shell document"]),
    (
        "social:description",
        [
            "Minimal placeholder",
            "Layout shell",
            "Content summary",
            "frame detail " + uuid.uuid4().hex[:4],
            "frame detail preview",
        ],
    ),
    (
        "twitter:site",
        ["@shell_app", "@DocFrame", "@LayoutViewer", "@frame_app", "@shell_stack"],
    ),
    (
        "twitter:title",
        ["Doc Shell", "Content Wrapper", "Frame_View", "Layout-Panel", "Shell Reader"],
    ),
    (
        "twitter:description",
        [
            "document shell preview",
            "layout frame - v1",
            "content-wrapper_" + uuid.uuid4().hex[:5],
            "frame builder beta",
            "document scaffold",
        ],
    ),
    ("al:web:url", ["https://example.com/app", "https://example.com/view"]),
    ("al:ios:url", ["fp-less://shell", "fp-less://viewer?id=123"]),
    ("al:ios:app_store_id", ["123456789", "987654321"]),
    ("al:ios:app_name", ["Shell Viewer", "Doc Frame"]),
    ("al:android:url", ["intent://shell#Intent", "fp-less://frame/123"]),
    ("al:android:package", ["com.fp.less.shell", "com.fp.less.frame"]),
    ("al:android:app_name", ["Shell Viewer", "Doc Frame"]),
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


def _format_attribute_pair(rng: random.Random, attr: str, value: str) -> str:
    attr_label = attr
    if maybe(rng, 0.22):
        attr_label = _randomize_case(rng, attr_label)
    left_eq_pad = " " if maybe(rng, 0.14) else ""
    right_eq_pad = " " if maybe(rng, 0.14) else ""
    return f'{attr_label}{left_eq_pad}={right_eq_pad}"{html.escape(value, quote=True)}"'


def _build_meta_tag(rng: random.Random, attr_name: str, name: str, content: str) -> str:
    attrs = [
        (attr_name, name),
        (pick(rng, ["content", "Content"]) if maybe(rng, 0.15) else "content", content),
    ]

    if maybe(rng, 0.28):
        rng.shuffle(attrs)

    attr_separator = pick(rng, [" ", "  ", "   "])
    prefix_space = pick(rng, [" ", "  "]) if maybe(rng, 0.35) else " "
    closing_pad = " " if maybe(rng, 0.25) else ""
    closing = pick(rng, ["/>", " />", ">", " >"])

    attr_fragments = [_format_attribute_pair(rng, attr, value) for attr, value in attrs]
    attr_block = attr_separator.join(attr_fragments)
    return f"<meta{prefix_space}{attr_block}{closing_pad}{closing}"


def meta_noise(rng: random.Random) -> str:
    n = rint(rng, 3, 9)
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
        name_key = (attr_name.lower(), name.lower())
        if name_key in seen_names and not maybe(rng, 0.45):
            continue
        content = pick(rng, values)
        if maybe(rng, 0.30):
            content = f"{content}-{uuid.uuid4().hex[:6]}"
        if attr_name == "name" and maybe(rng, 0.20):
            name = f"x-{name}" if not name.startswith("x-") else name
        if maybe(rng, 0.12):
            name = _randomize_case(rng, name)
        content = _format_meta_content(rng, content)
        tags.append(_build_meta_tag(rng, attr_name, name, content))
        if maybe(rng, 0.22):
            tags.append(_build_meta_tag(rng, attr_name, name, content))
        seen_names.add(name_key)

    return "".join(tags)
