from __future__ import annotations

import html
import random
import uuid
from datetime import datetime, timedelta
from typing import Callable

from .random_utils import maybe, pick, rfloat, rint


def _random_domain(rng: random.Random) -> str:
    tlds = ["com", "net", "org", "io", "app", "site", "dev", "page", "cloud"]
    syllables = [
        "meta",
        "frame",
        "shell",
        "doc",
        "view",
        "pane",
        "grid",
        "stack",
        "layer",
        "reader",
    ]
    labels = []
    for _ in range(rint(rng, 1, 2)):
        parts = [pick(rng, syllables) for _ in range(rint(rng, 1, 2))]
        label = "".join(parts)
        if maybe(rng, 0.40):
            label = f"{label}{rint(rng, 1, 999)}"
        labels.append(label)
    labels.append(pick(rng, tlds))
    return ".".join(labels)


def _random_url(rng: random.Random) -> str:
    prefix = pick(rng, ["https://", "http://", "https://www."])
    segments = []
    for _ in range(rint(rng, 1, 3)):
        segment = uuid.uuid4().hex[: rint(rng, 3, 8)]
        if maybe(rng, 0.30):
            segment = f"{segment}-{pick(rng, ['view', 'doc', 'frame', 'content'])}"
        segments.append(segment)
    path = "/".join(segments)
    if maybe(rng, 0.20):
        path = f"{path}?v={rint(rng, 1, 40)}"
    return f"{prefix}{_random_domain(rng)}/{path}"


def _random_person_name(rng: random.Random) -> str:
    first_names = [
        "Alex",
        "Jordan",
        "Casey",
        "Taylor",
        "Riley",
        "Avery",
        "Morgan",
    ]
    last_names = [
        "Kim",
        "Rivera",
        "Singh",
        "Patel",
        "Shaw",
        "Carson",
        "Ellis",
        "Knight",
    ]
    return f"{pick(rng, first_names)} {pick(rng, last_names)}"


def _random_date_string(rng: random.Random, year: int | None = None) -> str:
    now = datetime.now()
    year = now.year if year is None else year
    base = datetime(year, 1, 1)
    end_of_year = datetime(year + 1, 1, 1)
    upper_bound = min(end_of_year, now) if year == now.year else end_of_year
    span_seconds = max(1, int((upper_bound - base).total_seconds()))
    dt = base + timedelta(seconds=rint(rng, 0, span_seconds - 1))
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%SZ",
        "%a, %d %b %Y %H:%M:%S GMT",
    ]
    return dt.strftime(pick(rng, formats))


def noise_divs(rng: random.Random, nmax: int) -> str:
    n = rint(rng, 0, max(0, nmax))
    bits = []
    def random_rgba(alpha_min: float, alpha_max: float) -> str:
        r = rint(rng, 20, 240)
        g = rint(rng, 20, 240)
        b = rint(rng, 20, 240)
        a = rfloat(rng, alpha_min, alpha_max, 2)
        return f"rgba({r},{g},{b},{a})"

    def random_size() -> str:
        unit = pick(rng, ["px", "em", "rem", "%"])
        if unit == "%":
            value = rfloat(rng, 10.0, 100.0, 2)
        elif unit == "em":
            value = rfloat(rng, 0.4, 12.0, 2)
        elif unit == "rem":
            value = rfloat(rng, 0.5, 14.0, 2)
        else:
            value = rfloat(rng, 24.0, 260.0, 2)
        return f"{value}{unit}"

    for _ in range(n):

        h = rfloat(rng, 0.0, 8.5, 2)
        mt = rfloat(rng, 0.0, 8.5, 2)
        mb = rfloat(rng, 0.0, 8.5, 2)
        max_w = rfloat(rng, 80.0, 180.0, 2)
        styles = [f"height:{h}px", f"margin:{mt}px 0 {mb}px 0"]
        if maybe(rng, 0.45):
            styles.append(f"width:{random_size()}")
        if maybe(rng, 0.65):
            styles.append(f"max-width:{max_w}px")
        if maybe(rng, 0.45):
            min_w = rfloat(rng, 40.0, max(41.0, max_w - 10.0), 2)
            styles.append(f"min-width:{min_w}px")
        if maybe(rng, 0.35):
            display = pick(rng, ["block", "inline-block", "inline", "flex", "inline-flex"])
            styles.append(f"display:{display}")
            if display in {"flex", "inline-flex"} and maybe(rng, 0.70):
                styles.append(f"gap:{rfloat(rng, 0.0, 12.0, 2)}px")
        if maybe(rng, 0.30):
            styles.append(f"opacity:{rfloat(rng, 0.35, 0.95, 2)}")
        if maybe(rng, 0.30):
            styles.append(f"background-color:{random_rgba(0.02, 0.12)}")
        if maybe(rng, 0.22):
            if maybe(rng, 0.55):
                angle = rint(rng, 0, 360)
                styles.append(
                    "background-image:linear-gradient("
                    f"{angle}deg,{random_rgba(0.05, 0.2)},{random_rgba(0.05, 0.2)})"
                )
            else:
                x = rint(rng, 0, 100)
                y = rint(rng, 0, 100)
                styles.append(
                    "background-image:radial-gradient(circle at "
                    f"{x}% {y}%,{random_rgba(0.05, 0.2)},{random_rgba(0.05, 0.2)})"
                )
        if maybe(rng, 0.40):
            styles.append(f"border-radius:{rfloat(rng, 0.0, 6.0, 2)}px")
        if maybe(rng, 0.30):
            shadow_x = rfloat(rng, -4.0, 4.0, 2)
            shadow_y = rfloat(rng, -4.0, 4.0, 2)
            blur = rfloat(rng, 0.0, 12.0, 2)
            styles.append(f"box-shadow:{shadow_x}px {shadow_y}px {blur}px {random_rgba(0.06, 0.3)}")
        if maybe(rng, 0.28):
            styles.append(f"border:1px solid {random_rgba(0.05, 0.25)}")
        if maybe(rng, 0.20):
            styles.append(f"outline:1px solid {random_rgba(0.05, 0.25)}")
        if maybe(rng, 0.25):
            styles.append(f"min-height:{random_size()}")
        if maybe(rng, 0.25):
            styles.append(f"max-height:{random_size()}")
        if maybe(rng, 0.25):
            filters = []
            if maybe(rng, 0.65):
                filters.append(f"blur({rfloat(rng, 0.0, 1.6, 2)}px)")
            if maybe(rng, 0.65):
                filters.append(f"brightness({rfloat(rng, 0.7, 1.4, 2)})")
            if filters:
                styles.append(f"filter:{' '.join(filters)}")
        if maybe(rng, 0.35):
            transforms = []
            if maybe(rng, 0.70):
                tx = rfloat(rng, -6.0, 6.0, 2)
                ty = rfloat(rng, -6.0, 6.0, 2)
                transforms.append(f"translate({tx}px,{ty}px)")
            if maybe(rng, 0.60):
                transforms.append(f"rotate({rfloat(rng, -6.0, 6.0, 2)}deg)")
            if maybe(rng, 0.50):
                transforms.append(f"scale({rfloat(rng, 0.85, 1.15, 2)})")
            if maybe(rng, 0.40):
                transforms.append(
                    f"skew({rfloat(rng, -6.0, 6.0, 2)}deg,{rfloat(rng, -6.0, 6.0, 2)}deg)"
                )
            if transforms:
                styles.append(f"transform:{' '.join(transforms)}")

        attrs = []
        if maybe(rng, 0.80):
            attrs.append('aria-hidden="true"')
        if maybe(rng, 0.35):
            attrs.append('role="presentation"')
        if maybe(rng, 0.25):
            attrs.append(f'data-layer="{rint(rng, 0, 12)}"')
        if maybe(rng, 0.25):
            attrs.append(f'data-noise-kind="{pick(rng, ["grain", "speckle", "haze", "dust", "grid"])}"')
        if maybe(rng, 0.20):
            attrs.append(
                f'aria-label="{pick(rng, ["decorative", "layer", "noise", "spacer"])} {uuid.uuid4().hex[:4]}"'
            )
        if maybe(rng, 0.35):
            attrs.append(f'data-noise="{uuid.uuid4().hex[: rint(rng, 4, 8)]}"')

        attrs_str = f" {' '.join(attrs)}" if attrs else ""
        style_str = ";".join(styles)
        bits.append(f"<div{attrs_str} style=\"{style_str};\"></div>")
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
    (
        "application-name",
        [
            "Reader",
            "Letterbox",
            "HTML Shell",
            "DocFrame",
            lambda rng: f"{pick(rng, ['Shell', 'Frame', 'Layer'])}-{rint(rng, 10, 99)}",
        ],
    ),
    (
        "generator",
        [
            "fp-less-engine",
            "static-maker",
            "markup-crafter",
            "scribe-bundle",
            lambda rng: f"builder/{rint(rng, 1, 5)}.{rint(rng, 0, 9)}.{rint(rng, 0, 9)}",
        ],
    ),
    ("author", [lambda rng: _random_person_name(rng), "layout", "markup", "builder", "compose", "assembler"]),
    (
        "application-category",
        ["productivity", "utilities", "documentation", "offline-viewer", "notes"],
    ),
    (
        "keywords",
        [
            "letters, content, layout",
            "wrapper, document, reader",
            lambda rng: f"{pick(rng, ['shell', 'frame', 'panel'])},{pick(rng, ['reader', 'viewer'])},{pick(rng, ['offline', 'archive'])}",
        ],
    ),
    (
        "description",
        [
            "Document shell",
            "Layout wrapper",
            "Content frame",
            "Minimal placeholder",
            "Reader scaffold",
            lambda rng: f"{pick(rng, ['static document', 'content pane', 'layout view'])} {uuid.uuid4().hex[:5]}",
        ],
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
    ("google-site-verification", [lambda rng: uuid.uuid4().hex[: rint(rng, 16, 24)]]),
    ("msvalidate.01", [lambda rng: uuid.uuid4().hex[: rint(rng, 16, 24)]]),
    ("yandex-verification", [lambda rng: uuid.uuid4().hex[: rint(rng, 16, 24)]]),
    ("facebook-domain-verification", [lambda rng: uuid.uuid4().hex[: rint(rng, 16, 24)]]),
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
    ("application-version", ["1.0", "1.2.3", "2024.04", "0.9.0-beta", lambda rng: f"{rint(rng, 0, 3)}.{rint(rng, 0, 9)}.{rint(rng, 0, 9)}"]),
    ("build-id", [lambda rng: uuid.uuid4().hex[: rint(rng, 6, 12)]]),
    (
        "prefers-color-scheme",
        ["dark", "light", "light dark"],
    ),
    ("date", [lambda rng: _random_date_string(rng), lambda rng: _random_date_string(rng).split("T")[0]]),
    (
        "last-modified",
        [lambda rng: _random_date_string(rng), lambda rng: _random_date_string(rng).split("T")[0]],
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
    ("expires", [lambda rng: _random_date_string(rng)]),
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
    ("og:site_name", ["Document Shell", "Layout Frame", "Content Panel", "Shell Stack", lambda rng: f"{pick(rng, ['Shell', 'Frame', 'Layout'])} {rint(rng, 100, 999)}"]),
    (
        "og:title",
        [
            "Doc Shell",
            "Content Wrapper",
            "Frame_View",
            "Layout-Panel",
            "Reader Shell",
            lambda rng: f"{pick(rng, ['Content', 'Layout', 'Shell'])} {uuid.uuid4().hex[:4]}",
        ],
    ),
    (
        "og:description",
        [
            "Minimal placeholder",
            "Layout shell",
            "Content summary",
            "frame detail " + uuid.uuid4().hex[:4],
            "document wrapper preview",
            lambda rng: f"{pick(rng, ['Minimal placeholder', 'Layout shell', 'Content summary'])} {rint(rng, 1, 20)}",
        ],
    ),
    (
        "og:url",
        [
            lambda rng: _random_url(rng),
            lambda rng: f"https://{_random_domain(rng)}/docs/{uuid.uuid4().hex[:4]}",
            lambda rng: f"/{pick(rng, ['docs', 'viewer', 'embed'])}/{uuid.uuid4().hex[:4]}",
        ],
    ),
    (
        "og:image",
        [
            lambda rng: f"https://{_random_domain(rng)}/{uuid.uuid4().hex[:5]}.png",
            lambda rng: f"https://cdn.{_random_domain(rng)}/{uuid.uuid4().hex[:6]}/card.jpg",
            lambda rng: f"https://assets.{_random_domain(rng)}/cover-{rint(rng, 10, 99)}.jpg",
        ],
    ),
    ("og:image:alt", ["Document shell preview", "Layout preview", "Content card"]),
    ("og:determiner", ["the", "a", "an"]),
    ("article:published_time", [lambda rng: _random_date_string(rng)]),
    ("article:modified_time", [lambda rng: _random_date_string(rng)]),
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
    date_year = datetime.now().year

    def _date_or_date_only(rng: random.Random) -> str:
        date_value = _random_date_string(rng, year=date_year)
        formatter = pick(rng, [lambda v: v, lambda v: v.split("T")[0]])
        return formatter(date_value)

    date_generators: dict[tuple[str, str], Callable[[random.Random], str]] = {
        ("name", "date"): _date_or_date_only,
        ("name", "last-modified"): _date_or_date_only,
        ("http-equiv", "expires"): lambda rng: _random_date_string(rng, year=date_year),
        ("property", "article:published_time"): lambda rng: _random_date_string(rng, year=date_year),
        ("property", "article:modified_time"): lambda rng: _random_date_string(rng, year=date_year),
    }

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
        if name_key in seen_names:
            continue
        content = pick(rng, values)
        if callable(content):
            generator = date_generators.get(name_key)
            content = generator(rng) if generator else content(rng)
        if maybe(rng, 0.30):
            content = f"{content}-{uuid.uuid4().hex[:6]}"
        if attr_name == "name" and maybe(rng, 0.20):
            name = f"x-{name}" if not name.startswith("x-") else name
        if maybe(rng, 0.12):
            name = _randomize_case(rng, name)
        content = _format_meta_content(rng, content)
        tags.append(_build_meta_tag(rng, attr_name, name, content))
        seen_names.add(name_key)

    return "".join(tags)
