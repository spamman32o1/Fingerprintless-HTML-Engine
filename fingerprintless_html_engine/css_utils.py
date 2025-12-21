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

    layout_mode = pick(rng, ["block", "flow-root", "flex", "grid"])
    gap = rfloat(rng, 6.0, 14.0, 2)
    columns = 1
    uses_stacked_wrapper = False
    if layout_mode == "flex":
        flex_props = ["display:flex;", "flex-direction:column;", f"gap:{gap}px;"]
        uses_stacked_wrapper = True
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
        uses_stacked_wrapper = columns == 1
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

    likely_letter_layout = max_w <= 780.0 and pad <= 18.0 and line_height >= 1.45

    border_rad = rfloat(rng, 12.0, 20.0, 2)
    subtle_shadows = [
        "0 2px 6px rgba(0,0,0,0.04)",
        "0 4px 12px rgba(0,0,0,0.06)",
        "0 1px 3px rgba(0,0,0,0.05), 0 6px 14px rgba(15,23,42,0.06)",
    ]

    shadow = "none"
    if maybe(rng, 0.42):
        shadow = pick(
            rng,
            subtle_shadows
            + [
                "0 6px 18px rgba(0,0,0,0.07)",
                "0 10px 24px -12px rgba(15,23,42,0.22)",
                "inset 0 1px 0 rgba(255,255,255,0.65), 0 12px 28px rgba(15,23,42,0.12)",
            ],
        )

    if shadow == "none":
        shadow = pick(rng, subtle_shadows)
    pad += rfloat(rng, 1.5, 4.0, 2)

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

    accent_palette = [
        "#0ea5e9",
        "#2563eb",
        "#16a34a",
        "#d97706",
        "#e11d48",
        "#9333ea",
        "#0ea5e9",
        "#0f172a",
        text_color,
    ]

    underline_styles = [
        "underline solid",
        "underline dotted",
        "underline dashed",
        "underline double",
        "underline wavy",
    ]

    link_color = pick(rng, accent_palette)
    hover_color = pick(rng, accent_palette)
    active_color = pick(rng, accent_palette)
    underline = pick(rng, underline_styles)
    underline_thickness = rfloat(rng, 1.0, 2.4, 2)
    underline_offset = rfloat(rng, 1.5, 3.4, 2)

    transition_pool = [
        "transition: color 160ms ease, background-color 160ms ease, box-shadow 160ms ease;",
        "transition: all 180ms ease-in-out;",
        "transition: color 120ms linear, text-decoration-color 120ms linear;",
        "transition: transform 140ms ease, box-shadow 180ms ease;",
    ]
    transition_rule = pick(rng, transition_pool)

    link_rules = [
        f"color:{link_color};",
        f"text-decoration:{underline};",
        f"text-decoration-thickness:{underline_thickness}px;",
        f"text-underline-offset:{underline_offset}px;",
        transition_rule if maybe(rng, 0.70) else "",
    ]

    hover_rules = [f"color:{hover_color};"]
    if maybe(rng, 0.60):
        hover_rules.append("text-decoration-color: currentColor;")
    if maybe(rng, 0.22):
        hover_rules.append("transform: translateY(-0.5px);")

    active_rules = [f"color:{active_color};"]
    if maybe(rng, 0.36):
        active_rules.append("opacity:0.92;")

    extra_rules.append("a{" + "".join(link_rules) + "}")
    extra_rules.append("a:hover{" + "".join(hover_rules) + "}")
    extra_rules.append("a:active{" + "".join(active_rules) + "}")

    list_styles = [
        "disc",
        "circle",
        "square",
        "decimal",
        "lower-alpha",
        "upper-roman",
    ]
    list_style_type = pick(rng, list_styles)
    list_style_position = pick(rng, ["inside", "outside"])
    list_spacing = rfloat(rng, 0.35, 0.8, 2)
    extra_rules.append(
        "ul,ol{"
        + f"list-style-type:{list_style_type};"
        + f"list-style-position:{list_style_position};"
        + f"padding-left:{rfloat(rng, 16.0, 28.0, 2)}px;"
        + f"margin-block:{list_spacing}em;"
        + "}"
    )
    if maybe(rng, 0.30):
        extra_rules.append(
            "ul li::marker, ol li::marker{"
            + f"color:{pick(rng, accent_palette)};"
            + (f"font-size:{rfloat(rng, 1.0, 1.2, 2)}em;" if maybe(rng, 0.32) else "")
            + "}"
        )

    border_color = f"rgba(0,0,0,{rfloat(rng, 0.05, 0.14, 3)})"
    stripe_color = f"rgba(0,0,0,{rfloat(rng, 0.015, 0.06, 3)})"
    table_rule_parts = [
        "width:100%;",
        "border-collapse:collapse;" if maybe(rng, 0.55) else "border-collapse:separate;",
        f"border:{rfloat(rng, 0.5, 1.2, 2)}px solid {border_color};",
    ]
    extra_rules.append("table{" + "".join(table_rule_parts) + "}")
    cell_padding = rfloat(rng, 8.0, 14.0, 2)
    extra_rules.append(
        "th,td{"
        + f"padding:{cell_padding}px;"
        + f"border:{rfloat(rng, 0.4, 1.0, 2)}px solid {border_color};"
        + "text-align:left;"
        + "}"
    )
    extra_rules.append(
        "th{"
        + f"background-color:rgba(0,0,0,{rfloat(rng, 0.02, 0.06, 3)});"
        + ("font-weight:700;" if maybe(rng, 0.55) else "")
        + "}"
    )
    if maybe(rng, 0.60):
        extra_rules.append(
            "tbody tr:nth-child(even){"
            + f"background-color:{stripe_color};"
            + "}"
        )
    if maybe(rng, 0.28):
        extra_rules.append(
            "table caption{"
            + f"caption-side:{pick(rng, ['top', 'bottom'])};"
            + f"color:{pick(rng, accent_palette)};"
            + f"font-style:{pick(rng, ['normal', 'italic'])};"
            + "padding:6px;"
            + "}"
        )

    button_bg = pick(rng, accent_palette)
    button_fg = pick(rng, [text_color, "#ffffff", "#111827"])
    button_radius = rfloat(rng, 6.0, 12.0, 2)
    button_border = pick(
        rng,
        [
            "none",
            f"1px solid rgba(255,255,255,{rfloat(rng, 0.20, 0.45, 3)})",
            f"1px solid rgba(0,0,0,{rfloat(rng, 0.12, 0.24, 3)})",
        ],
    )
    button_shadow = pick(
        rng,
        [
            "none",
            f"0 4px 12px rgba(0,0,0,{rfloat(rng, 0.08, 0.18, 3)})",
            "inset 0 1px 0 rgba(255,255,255,0.45), 0 6px 14px rgba(0,0,0,0.10)",
        ],
    )

    button_rule = (
        "button,input[type=button],input[type=submit],input[type=reset]{"
        + f"background:{button_bg};"
        + f"color:{button_fg};"
        + f"border-radius:{button_radius}px;"
        + f"border:{button_border};"
        + f"padding:{rfloat(rng, 7.0, 11.0, 2)}px {rfloat(rng, 12.0, 18.0, 2)}px;"
        + f"font-weight:{pick(rng, ['500', '600', '700'])};"
        + f"box-shadow:{button_shadow};"
        + (transition_rule if maybe(rng, 0.75) else "")
        + "cursor:pointer;"
        + "}"
    )
    extra_rules.append(button_rule)

    button_hover = [f"background:{pick(rng, accent_palette)};"]
    if maybe(rng, 0.40):
        button_hover.append("transform:translateY(-1px);")
    if maybe(rng, 0.38):
        button_hover.append(
            f"box-shadow:0 8px 18px rgba(0,0,0,{rfloat(rng, 0.10, 0.20, 3)});"
        )
    extra_rules.append(
        "button:hover,input[type=button]:hover,input[type=submit]:hover,input[type=reset]:hover{"
        + "".join(button_hover)
        + "}"
    )
    button_active = [f"background:{pick(rng, accent_palette)};"]
    if maybe(rng, 0.44):
        button_active.append("transform:translateY(0px) scale(0.99);")
    if maybe(rng, 0.30):
        button_active.append("box-shadow:none;")
    extra_rules.append(
        "button:active,input[type=button]:active,input[type=submit]:active,input[type=reset]:active{"
        + "".join(button_active)
        + "}"
    )

    inline_accent_color = pick(rng, accent_palette)
    extra_rules.append(
        "small,sub,sup{"
        + f"color:{inline_accent_color};"
        + (f"font-weight:{pick(rng, ['500', '600'])};" if maybe(rng, 0.40) else "")
        + "letter-spacing:0.01em;"
        + "}"
    )
    extra_rules.append(
        "mark{"
        + f"background-color:rgba(255, 255, 0, {rfloat(rng, 0.25, 0.55, 3)});"
        + f"color:{pick(rng, [text_color, '#111827'])};"
        + "padding:0 2px;"
        + "border-radius:3px;"
        + "}"
    )
    extra_rules.append(
        "abbr{"
        + f"border-bottom:1px {pick(rng, ['dotted', 'dashed', 'solid'])} {inline_accent_color};"
        + f"text-decoration-color:{inline_accent_color};"
        + "text-decoration-skip-ink:auto;"
        + "cursor:help;"
        + "}"
    )
    if maybe(rng, 0.26):
        extra_rules.append(
            "cite,em{"
            + f"color:{pick(rng, accent_palette)};"
            + "font-style:italic;"
            + "}"
        )

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
        "white-space:nowrap;"
        f"transform:rotate({rot}deg);"
    )
