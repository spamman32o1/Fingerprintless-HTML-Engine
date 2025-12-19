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
