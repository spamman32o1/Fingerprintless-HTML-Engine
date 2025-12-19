from __future__ import annotations

import random

from .constants import BG_COLORS, FONT_STACKS, TEXT_COLORS
from .random_utils import maybe, pick, rfloat


def random_css(rng: random.Random) -> tuple[str, str, str]:
    base_font = pick(rng, FONT_STACKS)
    heading_font = None
    quote_font = None
    code_font = None

    heading_fonts = [
        '"Impact", "Haettenschweiler", "Franklin Gothic Bold", "Arial Black", sans-serif',
        '"Oswald", "Roboto Condensed", "Helvetica Condensed", "Arial Narrow", sans-serif',
        '"Bebas Neue", "League Gothic", "Oswald", "Inter", sans-serif',
        '"Montserrat", "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif',
        '"Roboto Slab", "Rockwell", "Clarendon", "Bookman", serif',
        '"Arvo", "Egyptienne", "Cambria", "Book Antiqua", serif',
        '"Arial Rounded MT Bold", "Segoe UI Rounded", Nunito, "Trebuchet MS", sans-serif',
        pick(rng, FONT_STACKS),
    ]
    quote_fonts = [
        '"Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", "Times New Roman", serif',
        "Georgia, 'Times New Roman', Times, serif",
        'ui-serif, "New York", "Times New Roman", serif',
        '"Roboto Slab", "Rockwell", "Clarendon", "Bookman", serif',
        '"Pacifico", "Segoe Script", "Comic Sans MS", "Brush Script MT", cursive',
        '"Patrick Hand", "Bradley Hand", "Segoe Print", "Comic Sans MS", cursive',
        '"Noto Serif CJK SC", "Songti SC", STSong, "SimSun", serif',
    ]
    code_fonts = [
        'ui-monospace, "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
        'Consolas, "Liberation Mono", "Courier New", monospace',
        '"JetBrains Mono", "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", monospace',
        '"Fira Code", "Source Code Pro", Menlo, Consolas, monospace',
        '"Cascadia Code", "Segoe UI Mono", "SFMono-Regular", Menlo, Consolas, monospace',
        '"IBM Plex Mono", "Source Code Pro", Menlo, Consolas, monospace',
    ]

    if maybe(rng, 0.55):
        heading_font = pick(rng, heading_fonts)
    if maybe(rng, 0.38):
        quote_font = pick(rng, quote_fonts)
    if maybe(rng, 0.50):
        code_font = pick(rng, code_fonts)

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

    body_background_images: list[str] = []
    gradient_options = [
        ("linear", "#fefefe", "#f7f8fb", 135),
        ("linear", "#fcfcfc", "#f5f6f8", 165),
        ("linear", "#faf9f7", "#f2f3f5", 95),
        ("linear", "#f7f8f6", "#eef0f2", 45),
        ("radial", "#f8f9fb", "#f2f4f6", 0),
    ]
    if maybe(rng, 0.30):
        g_type, c1, c2, angle = pick(rng, gradient_options)
        if g_type == "linear":
            body_background_images.append(
                f"linear-gradient({angle}deg, {c1} 0%, {c2} 100%)"
            )
        else:
            body_background_images.append(
                f"radial-gradient(circle at {pick(rng, ['20% 20%', '80% 15%', '50% 40%'])}, {c1} 0%, {c2} 70%)"
            )

    pattern_overlays = [
        "linear-gradient(120deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0) 30%, rgba(255,255,255,0.08) 60%, rgba(255,255,255,0) 90%)",
        "radial-gradient(circle at 25% 20%, rgba(0,0,0,0.03) 0%, rgba(0,0,0,0) 40%)",
        "linear-gradient(180deg, rgba(0,0,0,0.025) 0%, rgba(0,0,0,0) 35%, rgba(0,0,0,0.025) 70%, rgba(0,0,0,0) 100%)",
        "radial-gradient(circle at 80% 10%, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0) 36%)",
    ]
    if maybe(rng, 0.18):
        body_background_images.append(pick(rng, pattern_overlays))

    body_rules = [
        "margin: 0;",
        f"background-color: {bg_color};",
        f"color: {text_color};",
        f"font-family: {base_font};",
        f"font-size: {font_size}px;",
        f"line-height: {line_height};",
        f"letter-spacing: {letter_spacing}em;",
        f"word-spacing: {word_spacing}em;",
        f"opacity: {opacity};",
    ]

    if body_background_images:
        body_rules.append(f"background-image: {', '.join(body_background_images)};")
    if body_background_images and maybe(rng, 0.28):
        body_rules.append(f"background-size: {pick(rng, ['auto', '120% 120%', '90% 90%', '160% 160%'])};")

    body_css = " ".join(body_rules)

    border_rad = rfloat(rng, 12.0, 20.0, 2)
    border = "none"
    if maybe(rng, 0.55):
        border_styles = [
            f"1px solid rgba(127,127,127,{rfloat(rng, 0.16, 0.28, 3)})",
            f"1px dashed rgba(110,110,110,{rfloat(rng, 0.16, 0.24, 3)})",
            f"1px solid rgba(210,210,210,{rfloat(rng, 0.18, 0.30, 3)})",
            f"1px double rgba(120,120,120,{rfloat(rng, 0.14, 0.22, 3)})",
        ]
        border = pick(rng, border_styles)

    shadow = "none"
    if maybe(rng, 0.42):
        shadow = pick(
            rng,
            [
                "0 6px 18px rgba(0,0,0,0.07)",
                "0 10px 24px -12px rgba(15,23,42,0.22)",
                "0 3px 8px rgba(0,0,0,0.05), 0 1px 3px rgba(0,0,0,0.04)",
                "inset 0 1px 0 rgba(255,255,255,0.65), 0 12px 28px rgba(15,23,42,0.12)",
            ],
        )

    layout_mode = pick(rng, ["block", "flow-root", "flex", "grid"])
    gap = rfloat(rng, 6.0, 14.0, 2)
    if layout_mode == "flex":
        flex_props = ["display:flex;", "flex-direction:column;", f"gap:{gap}px;"]
        if maybe(rng, 0.24):
            flex_props.append(
                f"align-items:{pick(rng, ['stretch', 'flex-start', 'center'])};"
            )
        if maybe(rng, 0.22):
            flex_props.append(
                f"justify-content:{pick(rng, ['flex-start', 'space-between', 'center'])};"
            )
        extra = " ".join(flex_props)
    elif layout_mode == "grid":
        grid_props = ["display:grid;", f"gap:{gap}px;"]
        columns = rng.randint(1, 3)
        if columns > 1 and maybe(rng, 0.60):
            grid_props.append(
                f"grid-template-columns: repeat({columns}, minmax(0, 1fr));"
            )
        if maybe(rng, 0.30):
            grid_props.append(
                f"justify-items:{pick(rng, ['start', 'stretch', 'center'])};"
            )
        if maybe(rng, 0.22):
            grid_props.append(
                f"align-items:{pick(rng, ['start', 'stretch', 'center'])};"
            )
        extra = " ".join(grid_props)
    else:
        extra = f"display:{layout_mode};"

    text_align = None
    if maybe(rng, 0.18):
        text_align = pick(rng, ["start", "left", "center", "justify"])

    translate_x = rfloat(rng, -1.5, 1.5, 3) if maybe(rng, 0.16) else 0.0
    translate_y = rfloat(rng, -1.5, 1.5, 3) if maybe(rng, 0.16) else 0.0
    transforms = [
        f"rotate({rot}deg)",
        f"skewX({skew}deg)",
        f"scale({scale})",
    ]
    if translate_x or translate_y:
        transforms.insert(0, f"translate({translate_x}px, {translate_y}px)")

    wrapper_css = " ".join(
        [
            f"max-width: {max_w}px;",
            f"padding: {pad}px;",
            f"margin: {margin_top}px auto;",
            f"border-radius: {border_rad}px;",
            f"border: {border};",
            f"box-shadow: {shadow};",
            extra,
            f"transform: {' '.join(transforms)};",
            "transform-origin: top left;",
            f"text-align: {text_align};" if text_align else "",
        ]
    )

    extra_rules: list[str] = []
    if heading_font:
        heading_style: list[str] = [f"font-family:{heading_font};"]
        if maybe(rng, 0.45):
            heading_style.append(f"font-weight:{pick(rng, ['600', '700', '800', '900'])};")
        if maybe(rng, 0.18):
            heading_style.append("font-style:italic;")
        extra_rules.append("h1,h2,h3,h4,h5,h6{" + "".join(heading_style) + "}")
    if quote_font:
        quote_style: list[str] = [f"font-family:{quote_font};"]
        if maybe(rng, 0.40):
            quote_style.append(f"font-weight:{pick(rng, ['400', '500', '600'])};")
        if maybe(rng, 0.55):
            quote_style.append("font-style:italic;")
        extra_rules.append("blockquote{" + "".join(quote_style) + "}")
    if code_font:
        code_style: list[str] = [f"font-family:{code_font};"]
        if maybe(rng, 0.35):
            code_style.append(f"font-weight:{pick(rng, ['400', '500', '600'])};")
        if maybe(rng, 0.08):
            code_style.append("font-style:italic;")
        extra_rules.append("code,pre,kbd,samp{" + "".join(code_style) + "}")

    return body_css, wrapper_css, "".join(extra_rules)


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
