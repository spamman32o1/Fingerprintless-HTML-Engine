from __future__ import annotations

import random

from .constants import BG_COLORS, FONT_STACKS, TEXT_COLORS
from .random_utils import maybe, pick, rfloat


def random_css(rng: random.Random) -> tuple[str, str]:
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
