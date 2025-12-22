from __future__ import annotations

import random

from .constants import BG_COLORS, FONT_FAMILY_POOLS, TEXT_COLORS, VARIABLE_FONT_FAMILIES
from .random_utils import maybe, pick, rfloat


FONT_FALLBACKS = {
    "sans": ["system-ui", "-apple-system", '"Segoe UI"', "Arial", "sans-serif"],
    "serif": ['ui-serif', '"Times New Roman"', "Times", "serif"],
    "mono": ["ui-monospace", '"SFMono-Regular"', "Menlo", "monospace"],
    "cursive": ['"Comic Sans MS"', "cursive"],
    "cjk": ["system-ui", "sans-serif"],
    "display": ["system-ui", '"Segoe UI"', "Arial", "sans-serif"],
    "humanist": ["system-ui", '"Segoe UI"', "Arial", "sans-serif"],
    "slab": ['ui-serif', '"Times New Roman"', "Times", "serif"],
    "handwriting": ['"Comic Sans MS"', "cursive"],
}


def _build_font_stack(rng: random.Random, pool_key: str) -> tuple[str, bool]:
    pool = list(FONT_FAMILY_POOLS[pool_key])
    if not pool:
        return ", ".join(FONT_FALLBACKS[pool_key]), False

    count = min(len(pool), rng.randint(2, 4))
    families = rng.sample(pool, count)

    variable_fonts = VARIABLE_FONT_FAMILIES.get(pool_key, [])
    variable_used = False
    if variable_fonts and maybe(rng, 0.55):
        variable_family = pick(rng, variable_fonts)
        if variable_family not in families:
            insert_at = rng.randint(0, len(families))
            families.insert(insert_at, variable_family)
        variable_used = True
        if maybe(rng, 0.30) and len(variable_fonts) > 1:
            second_var = pick(rng, variable_fonts)
            if second_var not in families:
                families.insert(rng.randint(0, len(families)), second_var)
    elif variable_fonts and maybe(rng, 0.20):
        fallback_mix = pick(rng, variable_fonts)
        if fallback_mix not in families:
            families.append(fallback_mix)
        variable_used = True

    fallbacks = FONT_FALLBACKS[pool_key]
    existing = set(families)
    ordered = families + [fallback for fallback in fallbacks if fallback not in existing]
    variable_used = variable_used or any(family in variable_fonts for family in families)
    return ", ".join(ordered), variable_used


def _font_variation_settings(rng: random.Random) -> str:
    wght = rng.randint(350, 750)
    wdth = rng.randint(85, 115)
    slnt = rng.randint(-10, 0)
    return (
        'font-variation-settings: "wght" '
        f"{wght}, "
        '"wdth" '
        f"{wdth}, "
        '"slnt" '
        f"{slnt};"
    )


def _maybe_font_details(
    rng: random.Random,
    *,
    allow_variations: bool,
) -> list[str]:
    rules: list[str] = []
    if allow_variations and maybe(rng, 0.40):
        rules.append(_font_variation_settings(rng))
    if maybe(rng, 0.35):
        rules.append(f"font-optical-sizing:{pick(rng, ['auto', 'none'])};")
    if maybe(rng, 0.35):
        rules.append(f"font-kerning:{pick(rng, ['auto', 'normal', 'none'])};")
    if maybe(rng, 0.35):
        rules.append(f"font-stretch:{rfloat(rng, 85.0, 115.0, 1)}%;")
    return rules


def random_css(rng: random.Random) -> tuple[str, str, str]:
    base_pool = pick(rng, list(FONT_FAMILY_POOLS))
    base_font, base_is_variable = _build_font_stack(rng, base_pool)
    heading_font = None
    quote_font = None
    code_font = None
    heading_is_variable = False
    quote_is_variable = False
    code_is_variable = False

    heading_pool_choices = [
        "display",
        "sans",
        "serif",
        "humanist",
        "slab",
        "cursive",
        "cjk",
    ]
    quote_pool_choices = ["serif", "cursive", "cjk", "sans", "humanist", "handwriting"]
    code_pool_choices = ["mono", "mono", "mono", "humanist", "sans"]

    if maybe(rng, 0.55):
        heading_font, heading_is_variable = _build_font_stack(
            rng, pick(rng, heading_pool_choices)
        )
    if maybe(rng, 0.38):
        quote_font, quote_is_variable = _build_font_stack(
            rng, pick(rng, quote_pool_choices)
        )
    if maybe(rng, 0.50):
        code_font, code_is_variable = _build_font_stack(rng, pick(rng, code_pool_choices))

    font_size = (
        rfloat(rng, 11.5, 20.5, 2)
        if maybe(rng, 0.12)
        else rfloat(rng, 13.2, 17.4, 2)
    )
    line_height = (
        rfloat(rng, 1.05, 2.10, 3)
        if maybe(rng, 0.14)
        else rfloat(rng, 1.22, 1.78, 3)
    )
    letter_spacing = (
        rfloat(rng, -0.060, 0.080, 4)
        if maybe(rng, 0.16)
        else rfloat(rng, -0.024, 0.048, 4)
    )
    word_spacing = (
        rfloat(rng, -0.080, 0.300, 4)
        if maybe(rng, 0.16)
        else rfloat(rng, -0.030, 0.180, 4)
    )

    max_w = rfloat(rng, 640.0, 920.0, 2)
    pad = rfloat(rng, 8.0, 24.0, 2)
    margin_top = rfloat(rng, 6.0, 22.0, 2)

    dark_theme = maybe(rng, 0.24)
    text_palette = TEXT_COLORS if not dark_theme else [
        "#e5e7eb",
        "#f3f4f6",
        "#cbd5e1",
        "#f8fafc",
    ]
    bg_palette = BG_COLORS if not dark_theme else [
        "#0b1220",
        "#0f172a",
        "#111827",
        "#0d1117",
        "#13151a",
        "#161b22",
    ]

    opacity = rfloat(rng, 0.985, 1.0, 3) if maybe(rng, 0.12) else 1.0
    text_color = pick(rng, text_palette)
    bg_color = pick(rng, bg_palette)

    body_background_images: list[str] = []
    gradient_options = []
    if not dark_theme:
        gradient_options = [
            ("linear", "#fefefe", "#f7f8fb", 135),
            ("linear", "#fcfcfc", "#f5f6f8", 165),
            ("linear", "#faf9f7", "#f2f3f5", 95),
            ("linear", "#f7f8f6", "#eef0f2", 45),
            ("linear", "#fef7f1", "#f4f6f9", 120),
            ("linear", "#f9fbff", "#f1f3f8", 200),
            ("linear", "#d1d5db", "#f9fafb", 155),
            ("radial", "#f8f9fb", "#f2f4f6", 0),
            ("radial", "#fdfcfb", "#f4f4f6", 0),
        ]
    dark_gradients = [
        ("linear", "#0b1220", "#0f172a", 135),
        ("linear", "#0f172a", "#1e293b", 160),
        ("linear", "#111827", "#0d1117", 95),
        ("radial", "#0d1117", "#1f2937", 0),
        ("linear", "#13151a", "#0b1220", 25),
        ("linear", "#0f172a", "#312e81", 200),
    ]
    if dark_theme:
        gradient_options = dark_gradients
    if maybe(rng, 0.38 if dark_theme else 0.30):
        for _ in range(1 + (1 if maybe(rng, 0.25) else 0)):
            g_type, c1, c2, angle = pick(rng, gradient_options)
            if g_type == "linear":
                body_background_images.append(
                    f"linear-gradient({angle}deg, {c1} 0%, {c2} 100%)"
                )
            else:
                body_background_images.append(
                    f"radial-gradient(circle at {pick(rng, ['20% 20%', '80% 15%', '50% 40%'])}, {c1} 0%, {c2} 70%)"
                )

    if dark_theme:
        pattern_overlays = [
            "linear-gradient(120deg, rgba(255,255,255,0.025) 0%, rgba(255,255,255,0) 30%, rgba(255,255,255,0.035) 60%, rgba(255,255,255,0) 90%)",
            "radial-gradient(circle at 25% 20%, rgba(255,255,255,0.02) 0%, rgba(255,255,255,0) 40%)",
            "linear-gradient(180deg, rgba(15,23,42,0.16) 0%, rgba(15,23,42,0) 40%, rgba(15,23,42,0.12) 80%, rgba(15,23,42,0) 100%)",
            "radial-gradient(circle at 80% 10%, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0) 36%)",
            "repeating-linear-gradient(45deg, rgba(255,255,255,0.018) 0px, rgba(255,255,255,0.018) 1px, rgba(0,0,0,0) 1px, rgba(0,0,0,0) 12px)",
            "repeating-radial-gradient(circle at 10% 10%, rgba(255,255,255,0.02) 0px, rgba(255,255,255,0.02) 1px, rgba(0,0,0,0) 1px, rgba(0,0,0,0) 10px)",
            "linear-gradient(90deg, rgba(255,255,255,0.028) 0%, rgba(255,255,255,0) 35%, rgba(15,23,42,0.16) 70%, rgba(255,255,255,0) 100%)",
            "radial-gradient(circle at 10% 80%, rgba(255,255,255,0.025) 0%, rgba(255,255,255,0) 45%)",
        ]

        noise_textures = [
            "url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 120 120\"><filter id=\"n\"><feTurbulence type=\"fractalNoise\" baseFrequency=\"0.8\" numOctaves=\"4\" stitchTiles=\"stitch\"/></filter><rect width=\"120\" height=\"120\" filter=\"url(%23n)\" opacity=\"0.03\" fill=\"#cbd5e1\"/></svg>')",
            "url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 60 60\" shape-rendering=\"crispEdges\"><path d=\"M0 0h60v60H0z\" fill=\"none\"/><path d=\"M30 30h1v1h-1z\" fill=\"#e5e7eb\" opacity=\"0.04\"/><path d=\"M10 20h1v1h-1z\" fill=\"#cbd5e1\" opacity=\"0.035\"/></svg>')",
            "repeating-linear-gradient(135deg, rgba(255,255,255,0.015) 0px, rgba(255,255,255,0.015) 3px, rgba(255,255,255,0) 3px, rgba(255,255,255,0) 10px)",
        ]
    else:
        pattern_overlays = [
            "linear-gradient(120deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0) 30%, rgba(255,255,255,0.08) 60%, rgba(255,255,255,0) 90%)",
            "radial-gradient(circle at 25% 20%, rgba(0,0,0,0.03) 0%, rgba(0,0,0,0) 40%)",
            "linear-gradient(180deg, rgba(0,0,0,0.025) 0%, rgba(0,0,0,0) 35%, rgba(0,0,0,0.025) 70%, rgba(0,0,0,0) 100%)",
            "radial-gradient(circle at 80% 10%, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0) 36%)",
            "repeating-linear-gradient(45deg, rgba(0,0,0,0.02) 0px, rgba(0,0,0,0.02) 1px, rgba(255,255,255,0) 1px, rgba(255,255,255,0) 12px)",
            "repeating-radial-gradient(circle at 10% 10%, rgba(0,0,0,0.03) 0px, rgba(0,0,0,0.03) 1px, rgba(255,255,255,0) 1px, rgba(255,255,255,0) 10px)",
            "linear-gradient(90deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0) 35%, rgba(0,0,0,0.02) 70%, rgba(255,255,255,0) 100%)",
            "radial-gradient(circle at 10% 80%, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0) 45%)",
        ]

        noise_textures = [
            "url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 120 120\"><filter id=\"n\"><feTurbulence type=\"fractalNoise\" baseFrequency=\"0.8\" numOctaves=\"4\" stitchTiles=\"stitch\"/></filter><rect width=\"120\" height=\"120\" filter=\"url(%23n)\" opacity=\"0.05\"/></svg>')",
            "url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 60 60\" shape-rendering=\"crispEdges\"><path d=\"M0 0h60v60H0z\" fill=\"none\"/><path d=\"M30 30h1v1h-1z\" fill=\"white\" opacity=\"0.08\"/><path d=\"M10 20h1v1h-1z\" fill=\"white\" opacity=\"0.06\"/></svg>')",
            "repeating-linear-gradient(135deg, rgba(255,255,255,0.02) 0px, rgba(255,255,255,0.02) 3px, rgba(255,255,255,0) 3px, rgba(255,255,255,0) 10px)",
        ]

    if maybe(rng, 0.22):
        overlays = rng.sample(pattern_overlays, rng.randint(1, 2))
        body_background_images.extend(overlays)
    if maybe(rng, 0.18):
        body_background_images.append(pick(rng, noise_textures))

    use_css_vars = maybe(rng, 0.32)
    accent_candidates = [
        "#0ea5e9",
        "#2563eb",
        "#1d4ed8",
        "#38bdf8",
        "#22d3ee",
        "#16a34a",
        "#10b981",
        "#0f766e",
        "#d97706",
        "#f97316",
        "#e11d48",
        "#fb7185",
        "#c084fc",
        "#a855f7",
        "#14b8a6",
        "#fbbf24",
        text_color,
    ]
    if dark_theme:
        accent_candidates.extend(["#93c5fd", "#7dd3fc", "#f472b6", "#f59e0b", "#22c55e", "#c7d2fe"])
    accent_var = pick(rng, accent_candidates)
    bg_var = pick(rng, bg_palette)

    use_bg_var = use_css_vars and maybe(rng, 0.55)
    use_accent_var = use_css_vars and maybe(rng, 0.55)

    body_rules = [
        "margin: 0;",
        f"background-color: {'var(--bg)' if use_bg_var else bg_color};",
        f"color: {text_color};",
        f"font-family: {base_font};",
        f"font-size: {font_size}px;",
        f"line-height: {line_height};",
        f"letter-spacing: {letter_spacing}em;",
        f"word-spacing: {word_spacing}em;",
        f"opacity: {opacity};",
    ]
    if use_css_vars:
        body_rules.append(f"--accent: {accent_var};")
        body_rules.append(f"--bg: {bg_var};")
    if maybe(rng, 0.36):
        if base_is_variable and maybe(rng, 0.55):
            low = rng.randint(300, 480)
            high = rng.randint(low + 80, min(900, low + 420))
            body_rules.append(f"font-weight:{low} {high};")
        else:
            body_rules.append(f"font-weight:{rng.randint(300, 850)};")
    if maybe(rng, 0.26):
        if maybe(rng, 0.45):
            body_rules.append(f"font-style:oblique {rng.randint(6, 18)}deg;")
        else:
            body_rules.append(f"font-style:{pick(rng, ['normal', 'italic', 'oblique'])};")
    if maybe(rng, 0.18):
        body_rules.append(f"font-variant:{pick(rng, ['normal', 'small-caps'])};")
    if maybe(rng, 0.20):
        feature_value = pick(
            rng,
            ['"kern" 1, "liga" 1', '"liga" 1', '"kern" 1, "onum" 1', '"ss01" 1'],
        )
        body_rules.append(f"font-feature-settings:{feature_value};")
    if maybe(rng, 0.20):
        body_rules.append(
            f"text-rendering:{pick(rng, ['auto', 'optimizeLegibility', 'geometricPrecision'])};"
        )
    if maybe(rng, 0.14):
        body_rules.append(
            f"text-transform:{pick(rng, ['none', 'uppercase', 'lowercase', 'capitalize'])};"
        )
    if maybe(rng, 0.14):
        body_rules.append(f"hyphens:{pick(rng, ['none', 'manual', 'auto'])};")
    body_rules.extend(
        _maybe_font_details(
            rng,
            allow_variations=base_is_variable,
        )
    )

    if body_background_images:
        body_rules.append(f"background-image: {', '.join(body_background_images)};")
    if body_background_images and maybe(rng, 0.28):
        body_rules.append(f"background-size: {pick(rng, ['auto', '120% 120%', '90% 90%', '160% 160%'])};")
    if body_background_images and maybe(rng, 0.22):
        body_rules.append(
            f"background-position: {pick(rng, ['center', 'top left', 'top right', 'bottom left', 'bottom right'])};"
        )
    if body_background_images and maybe(rng, 0.18):
        body_rules.append(
            f"background-attachment: {pick(rng, ['scroll', 'fixed', 'local'])};"
        )

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

    pad_y = pad
    pad_x = pad
    pad_top = pad
    pad_bottom = pad
    pad_right = pad
    pad_left = pad
    if maybe(rng, 0.30):
        pad_y = rfloat(rng, 8.0, 26.0, 2)
        pad_x = rfloat(rng, 8.0, 26.0, 2)
    if maybe(rng, 0.22):
        pad_top = rfloat(rng, 6.0, 24.0, 2)
        pad_bottom = rfloat(rng, 6.0, 24.0, 2)
        pad_left = rfloat(rng, 6.0, 24.0, 2)
        pad_right = rfloat(rng, 6.0, 24.0, 2)

    margin_bottom = rfloat(rng, 8.0, 22.0, 2)
    margin_side = rfloat(rng, 0.0, 18.0, 2)
    margin_pattern = f"{margin_top}px auto"
    if maybe(rng, 0.30):
        margin_pattern = f"{margin_top}px auto {margin_bottom}px"
    if maybe(rng, 0.22):
        margin_pattern = f"{margin_top}px {margin_side}px {margin_bottom}px"

    wrapper_css = " ".join(
        [
            f"max-width: {max_w}px;",
            (
                f"padding: {pad_y}px {pad_x}px;"
                if maybe(rng, 0.55)
                else f"padding: {pad_top}px {pad_right}px {pad_bottom}px {pad_left}px;"
            ),
            f"margin: {margin_pattern};",
            f"border-radius: {border_rad}px;",
            f"border: {border};",
            f"box-shadow: {shadow};",
            extra,
            f"text-align: {text_align};" if text_align else "",
        ]
    )

    extra_rules: list[str] = []
    if heading_font:
        heading_style: list[str] = [f"font-family:{heading_font};"]
        if maybe(rng, 0.60):
            if heading_is_variable and maybe(rng, 0.55):
                low = rng.randint(450, 650)
                high = rng.randint(low + 40, min(950, low + 260))
                heading_style.append(f"font-weight:{low} {high};")
            else:
                heading_style.append(f"font-weight:{rng.randint(500, 900)};")
        if maybe(rng, 0.24):
            heading_style.append(
                f"font-style:{pick(rng, ['normal', 'italic', f'oblique {rng.randint(8, 16)}deg'])};"
            )
        heading_style.extend(
            _maybe_font_details(
                rng,
                allow_variations=heading_is_variable,
            )
        )
        extra_rules.append("h1,h2,h3,h4,h5,h6{" + "".join(heading_style) + "}")
    if quote_font:
        quote_style: list[str] = [f"font-family:{quote_font};"]
        if maybe(rng, 0.50):
            if quote_is_variable and maybe(rng, 0.55):
                low = rng.randint(350, 520)
                high = rng.randint(low + 60, min(850, low + 260))
                quote_style.append(f"font-weight:{low} {high};")
            else:
                quote_style.append(f"font-weight:{rng.randint(350, 750)};")
        if maybe(rng, 0.60):
            quote_style.append(
                f"font-style:{pick(rng, ['italic', f'oblique {rng.randint(6, 14)}deg', 'normal'])};"
            )
        quote_style.extend(
            _maybe_font_details(
                rng,
                allow_variations=quote_is_variable,
            )
        )
        extra_rules.append("blockquote{" + "".join(quote_style) + "}")
    if code_font:
        code_style: list[str] = [f"font-family:{code_font};"]
        if maybe(rng, 0.44):
            if code_is_variable and maybe(rng, 0.50):
                low = rng.randint(350, 520)
                high = rng.randint(low + 40, min(820, low + 200))
                code_style.append(f"font-weight:{low} {high};")
            else:
                code_style.append(f"font-weight:{rng.randint(350, 720)};")
        if maybe(rng, 0.14):
            code_style.append(
                f"font-style:{pick(rng, ['normal', 'italic', f'oblique {rng.randint(5, 12)}deg'])};"
            )
        code_style.extend(
            _maybe_font_details(
                rng,
                allow_variations=code_is_variable,
            )
        )
        extra_rules.append("code,pre,kbd,samp{" + "".join(code_style) + "}")

    accent_palette = [
        "#0ea5e9",
        "#2563eb",
        "#1d4ed8",
        "#38bdf8",
        "#22d3ee",
        "#16a34a",
        "#10b981",
        "#0f766e",
        "#d97706",
        "#f97316",
        "#e11d48",
        "#fb7185",
        "#9333ea",
        "#c084fc",
        "#a855f7",
        "#14b8a6",
        "#fbbf24",
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

    link_color = "var(--accent)" if use_accent_var and maybe(rng, 0.55) else pick(rng, accent_palette)
    hover_color = "var(--accent)" if use_accent_var and maybe(rng, 0.45) else pick(rng, accent_palette)
    active_color = "var(--accent)" if use_accent_var and maybe(rng, 0.35) else pick(rng, accent_palette)
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

    button_bg = "var(--accent)" if use_accent_var and maybe(rng, 0.40) else pick(rng, accent_palette)
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


def letter_style(rng: random.Random, *, allow_inline_block: bool = True) -> str:
    fs = rfloat(rng, 0.998, 1.008, 4)
    ls = rfloat(rng, -0.008, 0.020, 4)
    op = rfloat(rng, 0.970, 1.0, 3) if maybe(rng, 0.14) else 1.0

    # MUCH smaller/rarer position jitter
    dy = rfloat(rng, -0.12, 0.12, 3) if maybe(rng, 0.12) else 0.0

    rot = rfloat(rng, -0.20, 0.20, 3) if maybe(rng, 0.05) else 0.0

    display_rule = "display:inline;"
    if allow_inline_block and maybe(rng, 0.10):
        display_rule = "display:inline-block;vertical-align:middle;"

    whitespace_rule = ""
    if allow_inline_block and maybe(rng, 0.12):
        whitespace_rule = "white-space:nowrap;"

    font_variation = ""
    if maybe(rng, 0.05):
        font_variation = (
            'font-variation-settings:"wght" '
            f"{rng.randint(360, 640)};"
        )

    return (
        f"font-size:{fs}em;"
        f"letter-spacing:{ls}em;"
        f"opacity:{op};"
        f"{font_variation}"
        f"position:relative;top:{dy}px;"
        f"{display_rule}"
        f"{whitespace_rule}"
        f"transform:rotate({rot}deg);"
    )
