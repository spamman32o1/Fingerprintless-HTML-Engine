from __future__ import annotations

from dataclasses import dataclass, field
import random
import re

from .constants import FONT_FAMILY_POOLS, VARIABLE_FONT_FAMILIES
from .random_utils import maybe, pick, rfloat
from .tag_utils import is_strict_output_mode


COLOR_NAME_MAP = {
    "aqua": "#00ffff",
    "black": "#000000",
    "blue": "#0000ff",
    "fuchsia": "#ff00ff",
    "gray": "#808080",
    "green": "#008000",
    "grey": "#808080",
    "lime": "#00ff00",
    "maroon": "#800000",
    "navy": "#000080",
    "olive": "#808000",
    "purple": "#800080",
    "red": "#ff0000",
    "silver": "#c0c0c0",
    "teal": "#008080",
    "white": "#ffffff",
    "yellow": "#ffff00",
}
MIN_TEXT_BG_CONTRAST = 4.5
MIN_ACCENT_CONTRAST = 3.0


FONT_FALLBACKS = {
    "sans": ["system-ui", "-apple-system", "'Segoe UI'", "Arial", "sans-serif"],
    "serif": ["ui-serif", "'Times New Roman'", "Times", "serif"],
    "mono": ["ui-monospace", "'SFMono-Regular'", "Menlo", "monospace"],
    "cursive": ["'Comic Sans MS'", "cursive"],
    "cjk": ["system-ui", "sans-serif"],
    "display": ["system-ui", "'Segoe UI'", "Arial", "sans-serif"],
    "humanist": ["system-ui", "'Segoe UI'", "Arial", "sans-serif"],
    "slab": ["ui-serif", "'Times New Roman'", "Times", "serif"],
    "handwriting": ["'Comic Sans MS'", "cursive"],
}


@dataclass(frozen=True)
class InlineStyleRules:
    headings: tuple[tuple[str, str], ...] | None
    blockquote: tuple[tuple[str, str], ...] | None
    code: tuple[tuple[str, str], ...] | None
    link: tuple[tuple[str, str], ...]
    list_style: tuple[tuple[str, str], ...]
    table: tuple[tuple[str, str], ...]
    cell: tuple[tuple[str, str], ...]
    th: tuple[tuple[str, str], ...]
    table_stripe: tuple[tuple[str, str], ...] | None
    caption: tuple[tuple[str, str], ...] | None
    button: tuple[tuple[str, str], ...]
    small: tuple[tuple[str, str], ...]
    mark: tuple[tuple[str, str], ...]
    abbr: tuple[tuple[str, str], ...]
    cite_em: tuple[tuple[str, str], ...] | None


@dataclass(frozen=True)
class SourceColorContext:
    source_text_color: str | None = None
    source_bg_color: str | None = None
    dominant_text_candidates: tuple[str, ...] = tuple()
    dominant_bg_candidates: tuple[str, ...] = tuple()
    accent_candidates: tuple[str, ...] = tuple()
    gradient_candidates: tuple[str, ...] = tuple()
    overlay_candidates: tuple[str, ...] = tuple()
    body_styles: tuple[tuple[str, str], ...] = tuple()
    wrapper_styles: tuple[tuple[str, str], ...] = tuple()
    element_styles: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = tuple()
    has_source_styles: bool = False
    color_variants: tuple[tuple[str, str], ...] = field(default_factory=tuple, compare=False)


def parse_inline_style_declarations(style_value: str | None) -> dict[str, str]:
    declarations: dict[str, str] = {}
    if not style_value:
        return declarations
    for part in style_value.split(";"):
        if ":" not in part:
            continue
        prop, value = part.split(":", 1)
        prop = prop.strip().lower()
        if not prop:
            continue
        declarations[prop] = value.strip()
    return declarations


def _normalize_hex_color(value: str) -> str | None:
    value = value.strip().lstrip("#")
    if len(value) not in {3, 4, 6, 8} or not all(ch in "0123456789abcdefABCDEF" for ch in value):
        return None
    if len(value) in {3, 4}:
        value = "".join(ch * 2 for ch in value)
    if len(value) == 8 and value[6:] == "ff":
        value = value[:6]
    return f"#{value.lower()}"


def _parse_rgb_channel(value: str) -> int | None:
    value = value.strip()
    if value.endswith("%"):
        try:
            return max(0, min(255, round(float(value[:-1]) * 2.55)))
        except ValueError:
            return None
    try:
        return max(0, min(255, round(float(value))))
    except ValueError:
        return None


def _split_color_parts(value: str) -> list[str]:
    function_body = value[value.find("(") + 1 : -1].strip()
    if "," in function_body:
        return [part.strip() for part in function_body.split(",")]
    return [part for part in re.split(r"\s+|/", function_body) if part]


def _parse_alpha(value: str) -> float | None:
    try:
        alpha = float(value[:-1]) / 100 if value.endswith("%") else float(value)
    except ValueError:
        return None
    return max(0.0, min(1.0, alpha))


def _parse_hsl_color(value: str) -> str | None:
    parts = _split_color_parts(value)
    if len(parts) not in {3, 4}:
        return None
    try:
        hue = float(parts[0].removesuffix("deg")) % 360 / 360
        saturation = float(parts[1].removesuffix("%")) / 100
        lightness = float(parts[2].removesuffix("%")) / 100
    except ValueError:
        return None
    if not 0 <= saturation <= 1 or not 0 <= lightness <= 1:
        return None
    import colorsys

    channels = colorsys.hls_to_rgb(hue, lightness, saturation)
    return "#" + "".join(f"{round(channel * 255):02x}" for channel in channels)


def parse_color_value(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().lower()
    if value in {"", "inherit", "initial", "unset", "currentcolor", "none"}:
        return None
    if value == "transparent":
        return "#00000000"
    if value.startswith("#"):
        return _normalize_hex_color(value)
    if value in COLOR_NAME_MAP:
        return COLOR_NAME_MAP[value]
    if value.startswith(("rgb(", "rgba(")) and value.endswith(")"):
        parts = _split_color_parts(value)
        if len(parts) not in {3, 4}:
            return None
        alpha = _parse_alpha(parts[3]) if len(parts) == 4 else 1.0
        if alpha is None:
            return None
        channels = [_parse_rgb_channel(part) for part in parts[:3]]
        if any(channel is None for channel in channels):
            return None
        normalized = "#" + "".join(f"{channel:02x}" for channel in channels if channel is not None)
        return normalized if alpha >= 1.0 else normalized + f"{round(alpha * 255):02x}"
    if value.startswith(("hsl(", "hsla(")) and value.endswith(")"):
        normalized = _parse_hsl_color(value)
        parts = _split_color_parts(value)
        if normalized and len(parts) == 4:
            alpha = _parse_alpha(parts[3])
            if alpha is None:
                return None
            if alpha < 1.0:
                normalized += f"{round(alpha * 255):02x}"
        return normalized
    return None


def _color_to_rgba(value: str | None) -> tuple[int, int, int, float] | None:
    if not value:
        return None
    color = value.strip().lower()
    normalized = parse_color_value(color)
    if not normalized:
        return None
    rgb = tuple(int(normalized[index:index + 2], 16) for index in (1, 3, 5))
    alpha = 0.0 if color == "transparent" else 1.0
    if color.startswith(("rgba(", "hsla(")):
        parts = _split_color_parts(color)
        if len(parts) == 4:
            alpha = _parse_alpha(parts[3])
            if alpha is None:
                return None
    elif color.startswith("#") and len(color) == 5:
        alpha = int(color[4] * 2, 16) / 255
    elif color.startswith("#") and len(color) == 9:
        alpha = int(color[7:9], 16) / 255
    elif color.startswith(("rgb(", "hsl(")):
        parts = _split_color_parts(color)
        if len(parts) == 4:
            alpha = _parse_alpha(parts[3])
            if alpha is None:
                return None
    return (*rgb, alpha)


def _format_rgba(red: int, green: int, blue: int, alpha: float = 1.0) -> str:
    if alpha >= 0.9995:
        return f"#{red:02x}{green:02x}{blue:02x}"
    alpha_text = f"{alpha:.6f}".rstrip("0").rstrip(".")
    return f"rgba({red},{green},{blue},{alpha_text})"


def jitter_color(
    value: str | None,
    rng: random.Random | None,
    *,
    max_delta: int = 3,
    enabled: bool = True,
) -> str | None:
    """Perturb a source color, never its hue family or text opacity."""
    if value is None or not enabled or rng is None:
        return value
    rgba = _color_to_rgba(value)
    if rgba is None:
        return value
    red, green, blue, alpha = rgba
    channels = [
        max(0, min(255, channel + rng.randint(-max_delta, max_delta)))
        for channel in (red, green, blue)
    ]
    # Opacity is an authored readability/contrast decision; retain it exactly.
    if value.strip().lower().startswith("#") and len(value.strip()) in {5, 9}:
        return "#" + "".join(f"{channel:02x}" for channel in channels) + value.strip()[-2:]
    return _format_rgba(*channels, alpha)


def color_with_alpha(value: str, alpha: float) -> str:
    rgba = _color_to_rgba(value) or (127, 127, 127, 1.0)
    return _format_rgba(*rgba[:3], max(0.0, min(1.0, alpha)))


_HEX_COLOR_RE = re.compile(r"(?i)(?<![\w-])#([0-9a-f]{8}|[0-9a-f]{6}|[0-9a-f]{4}|[0-9a-f]{3})(?![0-9a-f])")
_COLOR_FUNCTION_RE = re.compile(r"(?i)(?<![\w-])((?:rgba?|hsla?)\([^()]*\))")
_COLOR_NAME_RE = re.compile(
    r"(?i)(?<![\w-])(" + "|".join(map(re.escape, COLOR_NAME_MAP)) + r")(?![\w-])"
)
_CSS_NUMBER_RE = re.compile(
    r"(?<![\w.#])-?(?:\d+(?:\.\d+)?|\.\d+)(px|pt|pc|em|rem|ex|ch|vw|vh|vmin|vmax|%|deg|ms|s)?(?![\w%])"
)
_PRESERVED_DECLARATIONS = {
    "animation", "animation-name", "content", "cursor", "display", "flex",
    "font-family", "font-feature-settings", "font-kerning", "font-optical-sizing",
    "font-style", "font-variant", "font-variation-settings", "font-weight",
    "list-style-type", "opacity", "order", "position", "text-rendering",
    "text-transform", "transition", "transition-property", "z-index",
}


def _format_number(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".") or "0"


def jitter_css_value(
    value: str,
    rng: random.Random | None,
    *,
    property_name: str = "",
    enabled: bool = True,
    jitter_colors: bool = True,
) -> str:
    """Jitter source colors and measurements while leaving URLs and keywords intact."""
    if not enabled or rng is None or not value or "url(" in value.lower() or "var(" in value.lower():
        return value
    prop = property_name.lower()
    if prop in _PRESERVED_DECLARATIONS or prop.startswith("--"):
        return value
    if prop in {"color", "background-color", "border-color", "outline-color", "text-decoration-color"}:
        return (jitter_color(value, rng) or value) if jitter_colors else value

    def replace_color(match: re.Match[str]) -> str:
        return jitter_color(match.group(0), rng) or match.group(0)

    updated = value
    if jitter_colors:
        updated = _HEX_COLOR_RE.sub(replace_color, updated)
        updated = _COLOR_FUNCTION_RE.sub(replace_color, updated)
        updated = _COLOR_NAME_RE.sub(replace_color, updated)

    protected_tokens: dict[str, str] = {}

    def protect_color(match: re.Match[str]) -> str:
        token = f"__source_color_{len(protected_tokens)}__"
        protected_tokens[token] = match.group(0)
        return token

    # Mapped rgba()/hex tokens must not be mistaken for geometry on a later pass.
    protected = _COLOR_FUNCTION_RE.sub(protect_color, updated)
    protected = _HEX_COLOR_RE.sub(protect_color, protected)

    def replace_number(match: re.Match[str]) -> str:
        number = float(match.group(0).removesuffix(match.group(1) or ""))
        unit = match.group(1) or ""
        if number == 0 or not unit:
            # Unitless values often encode flex, counts, ratios, or identifiers.
            return match.group(0)
        delta = min(0.35, abs(number) * 0.01) if unit in {"px", "pt", "pc"} else abs(number) * 0.005
        if unit == "deg":
            delta = 0.5
        if unit == "%" and (number <= 1 or number >= 99):
            return match.group(0)
        jittered = rfloat(rng, number - delta, number + delta, 3)
        if number > 0:
            jittered = max(0.0, jittered)
        return f"{_format_number(jittered)}{unit}"

    protected = _CSS_NUMBER_RE.sub(replace_number, protected)
    for token, color in protected_tokens.items():
        protected = protected.replace(token, color)
    return protected


def jitter_declarations(
    declarations: tuple[tuple[str, str], ...] | list[tuple[str, str]],
    rng: random.Random | None,
    *,
    enabled: bool = True,
    color_enabled: bool | None = None,
    source_color_context: SourceColorContext | None = None,
    color_variants: dict[str, str] | None = None,
) -> tuple[tuple[str, str], ...]:
    color_enabled = enabled if color_enabled is None else color_enabled
    variants = dict(source_color_context.color_variants) if source_color_context else {}
    if color_variants is not None:
        variants.update(color_variants)

    def map_colors(value: str) -> str:
        def replace(match: re.Match[str]) -> str:
            original = parse_color_value(match.group(0)) or ""
            if original not in variants:
                variants[original] = jitter_color(match.group(0), rng) or match.group(0)
            return variants[original]

        updated = _HEX_COLOR_RE.sub(replace, value)
        updated = _COLOR_FUNCTION_RE.sub(replace, updated)
        return _COLOR_NAME_RE.sub(replace, updated)

    return tuple(
        (
            name,
            jitter_css_value(
                map_colors(value) if color_enabled else value,
                rng,
                property_name=name,
                enabled=enabled,
                # Mapping has already perturbed every recognized color once.
                jitter_colors=False,
            ),
        )
        for name, value in declarations
    )


def declarations_text(declarations: tuple[tuple[str, str], ...] | list[tuple[str, str]]) -> str:
    return "".join(f"{name}:{value};" for name, value in declarations)


def _hex_to_rgb(color: str | None) -> tuple[int, int, int] | None:
    normalized = parse_color_value(color)
    if not normalized:
        return None
    return tuple(int(normalized[index:index + 2], 16) for index in (1, 3, 5))


def _relative_luminance(color: str | None) -> float | None:
    rgb = _hex_to_rgb(color)
    if rgb is None:
        return None
    def linearize(channel: int) -> float:
        value = channel / 255.0
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
    red, green, blue = (linearize(channel) for channel in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: str | None, second: str | None) -> float:
    first_luminance = _relative_luminance(first)
    second_luminance = _relative_luminance(second)
    if first_luminance is None or second_luminance is None:
        return 21.0
    lighter = max(first_luminance, second_luminance)
    darker = min(first_luminance, second_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def _is_light_color(color: str | None) -> bool | None:
    luminance = _relative_luminance(color)
    if luminance is None:
        return None
    return luminance >= 0.45


def _safe_text_for_bg(bg_color: str | None) -> str:
    return "#111111" if _is_light_color(bg_color) is not False else "#f5f5f5"


def prepare_source_colors(
    source_color_context: SourceColorContext,
    rng: random.Random | None,
    *,
    enabled: bool = True,
    color_variants: dict[str, str] | None = None,
) -> SourceColorContext:
    """Build one coordinated color mutation map for the entire variant."""
    raw_colors = (
        source_color_context.source_text_color,
        source_color_context.source_bg_color,
        *source_color_context.dominant_text_candidates,
        *source_color_context.dominant_bg_candidates,
        *source_color_context.accent_candidates,
    )
    raw_colors += tuple(
        raw_color
        for declarations in (
            source_color_context.body_styles,
            source_color_context.wrapper_styles,
            *(styles for _, styles in source_color_context.element_styles),
        )
        for _, value in declarations
        for raw_color in _gradient_color_values(value)
    )
    original_colors = dict.fromkeys(
        color for raw_color in raw_colors
        if (color := parse_color_value(raw_color))
    )
    color_map = dict(color_variants or {})
    for color in original_colors:
        if color not in color_map:
            color_map[color] = jitter_color(color, rng, enabled=enabled) or color
    if color_variants is not None:
        color_variants.update(color_map)

    def mapped(colors: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(color_map.get(color, jitter_color(color, rng, enabled=enabled) or color) for color in colors)

    def mapped_gradient(value: str) -> str:
        return jitter_declarations(
            (("background-image", value),),
            rng,
            enabled=enabled,
            source_color_context=source_color_context,
            color_variants=color_variants,
        )[0][1]

    def mapped_declarations(
        declarations: tuple[tuple[str, str], ...],
    ) -> tuple[tuple[str, str], ...]:
        result = []
        for name, value in declarations:
            variant = dict(color_map)
            variant.update({
                original: jitter_color(original, rng, enabled=enabled) or original
                for original in _gradient_color_values(value)
                if original not in variant
            })
            result.append((name, _replace_known_colors(value, variant)))
        return tuple(result)

    return SourceColorContext(
        source_text_color=(
            color_map.get(source_color_context.source_text_color or "")
            or source_color_context.source_text_color
        ),
        source_bg_color=(
            color_map.get(source_color_context.source_bg_color or "")
            or source_color_context.source_bg_color
        ),
        dominant_text_candidates=mapped(source_color_context.dominant_text_candidates),
        dominant_bg_candidates=mapped(source_color_context.dominant_bg_candidates),
        accent_candidates=mapped(source_color_context.accent_candidates),
        gradient_candidates=tuple(mapped_gradient(value) for value in source_color_context.gradient_candidates),
        overlay_candidates=tuple(mapped_gradient(value) for value in source_color_context.overlay_candidates),
        body_styles=mapped_declarations(source_color_context.body_styles),
        wrapper_styles=mapped_declarations(source_color_context.wrapper_styles),
        element_styles=tuple(
            (key, mapped_declarations(styles))
            for key, styles in source_color_context.element_styles
        ),
        has_source_styles=source_color_context.has_source_styles,
        color_variants=tuple(color_map.items()),
    )


def coordinated_color(
    source_color_context: SourceColorContext,
    value: str | None,
    rng: random.Random | None,
    *,
    fallback: str,
    enabled: bool = True,
) -> str:
    """Reuse a variant color when present; bound fallback colors to the same source."""
    if value:
        mapped = variant_color(source_color_context, value, "")
        if mapped:
            return mapped
    return jitter_color(fallback, rng, enabled=enabled) or fallback


def _replace_known_colors(value: str, variants: dict[str, str]) -> str:
    # Work from concrete source values so identical colors remain identical everywhere.
    def hex_replacement(match: re.Match[str]) -> str:
        return variants.get(parse_color_value(match.group(0)) or "", match.group(0))

    updated = _HEX_COLOR_RE.sub(hex_replacement, value)

    def function_replacement(match: re.Match[str]) -> str:
        return variants.get(parse_color_value(match.group(0)) or "", match.group(0))

    updated = _COLOR_FUNCTION_RE.sub(function_replacement, updated)
    return _COLOR_NAME_RE.sub(function_replacement, updated)


def _gradient_color_values(value: str) -> tuple[str, ...]:
    colors = [parse_color_value(match.group(0)) for match in _HEX_COLOR_RE.finditer(value)]
    colors.extend(parse_color_value(match.group(0)) for match in _COLOR_FUNCTION_RE.finditer(value))
    colors.extend(parse_color_value(match.group(0)) for match in _COLOR_NAME_RE.finditer(value))
    return tuple(color for color in colors if color)


def variant_color(
    source_color_context: SourceColorContext,
    value: str | None,
    fallback: str,
) -> str:
    if value:
        variants = dict(source_color_context.color_variants)
        normalized = parse_color_value(value)
        if normalized and normalized in variants:
            return variants[normalized]
        if parse_color_value(value):
            return value
    return fallback


def _rules_to_inline(rule_text: str) -> tuple[tuple[str, str], ...]:
    if not rule_text:
        return tuple()
    inline: list[tuple[str, str]] = []
    for part in rule_text.split(";"):
        if not part.strip():
            continue
        if ":" not in part:
            continue
        prop, value = part.split(":", 1)
        inline.append((prop.strip(), value.strip()))
    return tuple(inline)


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
    stack = ", ".join(ordered)
    return stack.replace('"', "'"), variable_used


def _font_variation_settings(rng: random.Random) -> str:
    wght = rng.randint(380, 620)
    wdth = rng.randint(92, 108)
    slnt = rng.randint(-6, 0)
    return (
        "font-variation-settings: 'wght' "
        f"{wght}, "
        "'wdth' "
        f"{wdth}, "
        "'slnt' "
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
    if maybe(rng, 0.12):
        rules.append(f"font-stretch:{rfloat(rng, 95.0, 105.0, 1)}%;")
    return rules


def random_css(
    rng: random.Random,
    output_mode: str = "default",
    *,
    allow_dark_mode: bool = True,
    enable_css_randomization: bool = True,
    enable_font_css: bool = True,
    enable_font_randomization: bool = True,
    enable_font_features: bool = True,
    enable_gradients: bool = True,
    enable_noise_textures: bool = True,
    enable_color_palette_randomization: bool = True,
    enable_body_styles: bool = True,
    source_color_context: SourceColorContext | None = None,
) -> tuple[str, str, str, InlineStyleRules]:
    strict_mode = is_strict_output_mode(output_mode)
    super_strict = output_mode in {"super_strict", "libero"}
    if not enable_css_randomization:
        enable_font_randomization = False
        enable_gradients = False
        enable_noise_textures = False
        enable_font_features = False
        rng = random.Random(0)
    if not enable_font_css:
        enable_font_randomization = False
        enable_font_features = False

    source_color_context = (
        source_color_context
        if source_color_context and source_color_context.color_variants
        else prepare_source_colors(
            source_color_context or SourceColorContext(),
            rng,
            enabled=enable_color_palette_randomization,
        )
    )
    source_styles = dict(source_color_context.element_styles)
    color_rng = rng if enable_color_palette_randomization else None
    metric_rng = rng if enable_css_randomization else None

    def _source_value(key: str, *names: str) -> str | None:
        styles = source_styles.get(key, ())
        values = dict(styles)
        return next((values[name] for name in names if values.get(name)), None)

    def _contrast_safe_colors(
        palette: list[str],
        *,
        background: str | None,
        minimum_contrast: float = 0.0,
        preserve_color: str | None = None,
    ) -> list[str]:
        candidates: list[str] = []
        seen: set[str] = set()
        for color in [preserve_color, *palette]:
            parsed = parse_color_value(color)
            if not parsed or parsed in seen:
                continue
            seen.add(parsed)
            if background and contrast_ratio(parsed, background) < minimum_contrast:
                continue
            candidates.append(parsed)
        return candidates

    def _pick_color(
        palette: list[str],
        *,
        background: str | None = None,
        minimum_contrast: float = 0.0,
        preserve_color: str | None = None,
        fallback: str | None = None,
    ) -> str:
        candidates = _contrast_safe_colors(
            palette,
            background=background,
            minimum_contrast=minimum_contrast,
            preserve_color=preserve_color,
        )

        preserved = parse_color_value(preserve_color)
        if preserved and (
            not background or contrast_ratio(preserved, background) >= minimum_contrast
        ):
            return preserved

        if not candidates:
            return parse_color_value(fallback) or "#111111"
        if not enable_color_palette_randomization:
            return candidates[0]
        # Prefer the source-derived candidate over arbitrary list entries.
        return candidates[0]

    source_font = _source_value("body", "font-family") or dict(source_color_context.body_styles).get("font-family")
    base_font = ""
    base_is_variable = False
    if enable_font_css:
        base_pool = (
            pick(rng, ["sans", "serif", "humanist", "slab", "cjk", "mono"])
            if enable_font_randomization and not source_font and not source_color_context.has_source_styles
            else "sans"
        )
        base_font, base_is_variable = (
            _build_font_stack(rng, base_pool)
            if enable_font_randomization and not source_font and not source_color_context.has_source_styles
            else (source_font or ", ".join(FONT_FALLBACKS["sans"]), False)
        )
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

    if enable_font_css and enable_font_randomization and not source_styles and not _source_value("headings", "font-family") and maybe(rng, 0.55):
        heading_font, heading_is_variable = _build_font_stack(
            rng, pick(rng, heading_pool_choices)
        )
    if enable_font_css and enable_font_randomization and not source_styles and not _source_value("blockquote", "font-family") and maybe(rng, 0.38):
        quote_font, quote_is_variable = _build_font_stack(
            rng, pick(rng, quote_pool_choices)
        )
    if enable_font_css and enable_font_randomization and not source_styles and not _source_value("code", "font-family") and maybe(rng, 0.50):
        code_font, code_is_variable = _build_font_stack(rng, pick(rng, code_pool_choices))

    font_size = None
    line_height = None
    letter_spacing = None
    word_spacing = None
    if enable_font_css:
        source_font_size = _source_value("body", "font-size")
        font_size = (
            rfloat(rng, 15.8, 16.2, 2)
            if enable_font_randomization and not source_font_size
            else rfloat(rng, 15.9, 16.1, 2)
        )
        line_height = 1.4 if output_mode in {"default", "strict", "super_strict", "libero"} else 1.5
        letter_spacing = rfloat(rng, -0.001, 0.001, 4)
        word_spacing = rfloat(rng, -0.001, 0.001, 4)

    max_w = rfloat(rng, 598.0, 602.0, 2)
    source_wrapper = dict(source_color_context.wrapper_styles)
    pad = rfloat(rng, 11.8, 12.2, 2)
    margin_top = rfloat(rng, 11.8, 12.2, 2)
    if source_wrapper:
        wrapper_padding = jitter_css_value(source_wrapper.get("padding", "12px"), metric_rng, property_name="padding")
        wrapper_margin = jitter_css_value(source_wrapper.get("margin", "12px auto"), metric_rng, property_name="margin")
    else:
        wrapper_padding = f"{pad}px"
        wrapper_margin = f"{margin_top}px auto"

    source_bg_color = source_color_context.source_bg_color
    source_text_color = source_color_context.source_text_color
    dark_theme = _is_light_color(source_bg_color) is False
    bg_color = coordinated_color(
        source_color_context,
        source_bg_color,
        color_rng,
        fallback="#ffffff" if allow_dark_mode or not dark_theme else "#111111",
        enabled=enable_color_palette_randomization,
    )
    text_color = coordinated_color(
        source_color_context,
        source_text_color,
        color_rng,
        fallback="#111111" if not dark_theme else "#f5f5f5",
        enabled=enable_color_palette_randomization,
    )
    if source_text_color and source_bg_color and contrast_ratio(text_color, bg_color) < MIN_TEXT_BG_CONTRAST:
        text_color = _safe_text_for_bg(bg_color)
    opacity = 1.0
    bg_candidates = list(dict.fromkeys([*source_color_context.dominant_bg_candidates, bg_color]))
    text_candidates = list(dict.fromkeys([*source_color_context.dominant_text_candidates, text_color]))

    body_background_images: list[str] = []
    if enable_gradients and not source_color_context.has_source_styles and not source_color_context.body_styles and maybe(rng, 0.30):
        angle = rfloat(rng, 88.0, 92.0, 3) if metric_rng else 90.0
        gradient_start = jitter_color(bg_color, color_rng) or bg_color
        gradient_end = jitter_color(bg_color, color_rng) or bg_color
        body_background_images.append(
            f"linear-gradient({_format_number(angle)}deg, {gradient_start} 0%, {gradient_end} 100%)"
        )

    pattern_color = accent_var = coordinated_color(
        source_color_context,
        source_color_context.accent_candidates[0] if source_color_context.accent_candidates else None,
        color_rng,
        fallback=text_color if contrast_ratio(text_color, bg_color) >= MIN_ACCENT_CONTRAST else _safe_text_for_bg(bg_color),
        enabled=enable_color_palette_randomization,
    )

    def pattern_overlay() -> str:
        angle = rfloat(rng, 43.0, 47.0, 3) if metric_rng else 45.0
        start = rfloat(rng, 0.25, 0.75, 3) if metric_rng else 0.5
        period = rfloat(rng, 11.5, 12.5, 3) if metric_rng else 12.0
        alpha = rfloat(rng, 0.004, 0.012, 4) if metric_rng else 0.008
        return (
            f"repeating-linear-gradient({_format_number(angle)}deg,"
            f"{color_with_alpha(pattern_color, alpha)} 0px,"
            f"{color_with_alpha(pattern_color, alpha)} {_format_number(start)}px,"
            f"{color_with_alpha(pattern_color, 0)} {_format_number(start)}px,"
            f"{color_with_alpha(pattern_color, 0)} {_format_number(period)}px)"
        )

    def noise_texture() -> str:
        size = rint(rng, 118, 122) if metric_rng else 120
        frequency = rfloat(rng, 0.79, 0.81, 4) if metric_rng else 0.8
        octaves = rint(rng, 3, 4) if metric_rng else 4
        opacity = rfloat(rng, 0.006, 0.016, 4) if metric_rng else 0.01
        texture_color = jitter_color(pattern_color, color_rng) or pattern_color
        return (
            "url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" "
            f"viewBox=\"0 0 {size} {size}\"><filter id=\"n\"><feTurbulence "
            f"type=\"fractalNoise\" baseFrequency=\"{frequency}\" numOctaves=\"{octaves}\" "
            f"stitchTiles=\"stitch\"/></filter><rect width=\"{size}\" height=\"{size}\" "
            f"filter=\"url(%23n)\" opacity=\"{opacity}\" fill=\"{texture_color}\"/></svg>')"
        )

    if source_color_context.overlay_candidates and not source_color_context.body_styles:
        body_background_images.extend(source_color_context.overlay_candidates)
    elif not source_color_context.has_source_styles and not source_color_context.body_styles and maybe(rng, 0.22):
        body_background_images.append(pattern_overlay())
    if enable_noise_textures and not source_color_context.has_source_styles and not source_color_context.body_styles and maybe(rng, 0.18):
        body_background_images.append(noise_texture())

    use_css_vars = maybe(rng, 0.32) if enable_body_styles and not source_color_context.body_styles else False
    accent_candidates = [*source_color_context.accent_candidates, accent_var]

    bg_var = _pick_color(bg_candidates, preserve_color=bg_color, fallback=bg_color)

    use_bg_var = use_css_vars and maybe(rng, 0.55)
    use_accent_var = use_css_vars and maybe(rng, 0.55)

    body_css = ""
    if enable_body_styles:
        source_body = source_styles.get("body", source_color_context.body_styles)
        body_rules = []
        present_body = {name for name, _ in source_body}
        if not source_body and "background-color" not in present_body and "background" not in present_body:
            body_rules.append(f"background-color: {'var(--bg)' if use_bg_var else bg_color};")
        if not source_body and "color" not in present_body:
            body_rules.append(f"color: {text_color};")
        if "opacity" not in present_body and not source_body:
            body_rules.append(f"opacity: {opacity};")
        if enable_font_css and not source_body:
            for name, value in (
                ("font-family", base_font),
                ("font-size", f"{font_size}px"),
                ("line-height", str(line_height)),
                ("letter-spacing", f"{letter_spacing}em"),
                ("word-spacing", f"{word_spacing}em"),
            ):
                body_rules.append(f"{name}: {value};")
        if not source_body and use_css_vars:
            body_rules.append(f"--accent: {accent_var};")
            body_rules.append(f"--bg: {bg_var};")
        if enable_font_css and enable_font_features and not source_body and not source_color_context.has_source_styles:
            if maybe(rng, 0.20):
                feature_value = pick(
                    rng,
                    ["'kern' 1, 'liga' 1", "'liga' 1", "'kern' 1, 'onum' 1"],
                )
                body_rules.append(f"font-feature-settings:{feature_value};")
            if enable_font_features:
                body_rules.extend(
                    _maybe_font_details(rng, allow_variations=False)
                )

        if body_background_images and not source_body and not super_strict and "background-image" not in present_body:
            body_rules.append(f"background-image: {', '.join(dict.fromkeys(body_background_images))};")
        if body_background_images and not source_body and not super_strict and "background-size" not in present_body and maybe(rng, 0.28):
            body_rules.append(f"background-size: {rfloat(rng, 99.5, 100.5, 2)}% {rfloat(rng, 99.5, 100.5, 2)}%;")
        if body_background_images and not source_body and not super_strict and "background-position" not in present_body and maybe(rng, 0.22):
            body_rules.append(f"background-position: {rfloat(rng, 49.5, 50.5, 2)}% {rfloat(rng, 49.5, 50.5, 2)}%;")

        body_css = " ".join(body_rules)

    border_rad = rfloat(metric_rng, 3.98, 4.02, 3) if metric_rng else 4.0
    layout_mode = "block" if strict_mode else pick(rng, ["block", "flow-root"])
    extra = f"display:{layout_mode};"
    wrapper_rules = []
    if source_styles.get("wrapper"):
        wrapper_rules.extend(
            f"{name}:{jitter_css_value(value, metric_rng, property_name=name, jitter_colors=False)};"
            for name, value in source_styles["wrapper"]
        )
    else:
        wrapper_rules.append(f"padding:{wrapper_padding};margin:{wrapper_margin};")
        if not source_color_context.has_source_styles:
            wrapper_rules.append(f"border-radius:{border_rad}px;")
        if not strict_mode and not source_color_context.has_source_styles:
            wrapper_rules.append(f"max-width:{max_w}px;")
        if not source_color_context.has_source_styles and maybe(rng, 0.4):
            wrapper_rules.append(
                f"border:1px solid {color_with_alpha(accent_var, rfloat(rng, 0.012, 0.026, 4))};"
            )
        if not source_color_context.has_source_styles and maybe(rng, 0.4):
            shadow_y = rfloat(rng, 0.75, 1.25, 3) if metric_rng else 1.0
            shadow_blur = rfloat(rng, 2.75, 3.25, 3) if metric_rng else 3.0
            wrapper_rules.append(
                f"box-shadow:0 {shadow_y}px {shadow_blur}px {color_with_alpha(accent_var, 0.018)};"
            )
        wrapper_rules.append(extra)
    wrapper_css = " ".join(wrapper_rules)

    extra_rules: list[str] = []
    heading_inline: tuple[tuple[str, str], ...] | None = None
    quote_inline: tuple[tuple[str, str], ...] | None = None
    code_inline: tuple[tuple[str, str], ...] | None = None
    if enable_font_css and heading_font and not source_color_context.has_source_styles and not source_styles.get("headings"):
        heading_style = [f"font-family:{heading_font};"]
        heading_style_text = "".join(heading_style)
        extra_rules.append("h1,h2,h3,h4,h5,h6{" + heading_style_text + "}")
        heading_inline = _rules_to_inline(heading_style_text)
    if enable_font_css and quote_font and not source_color_context.has_source_styles and not source_styles.get("blockquote"):
        quote_style_text = f"font-family:{quote_font};"
        extra_rules.append("blockquote{" + quote_style_text + "}")
        quote_inline = _rules_to_inline(quote_style_text)
    if enable_font_css and code_font and not source_color_context.has_source_styles and not source_styles.get("code"):
        code_style_text = f"font-family:{code_font};"
        extra_rules.append("code,pre,kbd,samp{" + code_style_text + "}")
        code_inline = _rules_to_inline(code_style_text)

    def _element_style(key: str, defaults: list[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
        if source_styles.get(key):
            return tuple(
                (name, jitter_css_value(value, metric_rng, property_name=name, jitter_colors=False))
                for name, value in source_styles[key]
            )
        return tuple(
            (name, jitter_css_value(value, metric_rng, property_name=name))
            for name, value in defaults
        )

    link_color = coordinated_color(source_color_context, accent_var, color_rng, fallback=text_color)
    link_style_text = declarations_text(_element_style("link", [
        ("color", link_color), ("text-decoration", "underline"),
        ("text-decoration-thickness", "1px"), ("text-underline-offset", "2px"),
    ]))
    if not source_styles.get("link"):
        extra_rules.append("a{" + link_style_text + "}")
    hover_color = jitter_color(link_color, color_rng) or link_color
    hover_rules = f"color:{hover_color};"
    if not source_styles.get("link"):
        for pseudo in (":hover", ":focus", ":focus-visible", ":active"):
            extra_rules.append(f"a{pseudo}{{{hover_rules}}}")

    list_style_text = declarations_text(_element_style("list", [
        ("padding-left", "20px"), ("margin-block", "0.5em"),
    ]))
    if not source_styles.get("list"):
        extra_rules.append("ul,ol{" + list_style_text + "}")
    if not source_styles.get("list") and maybe(rng, 0.30):
        extra_rules.append(f"ul li::marker, ol li::marker{{color:{accent_var};}}")

    table_style_text = declarations_text(_element_style("table", [
        ("width", "100%"), ("border-collapse", "collapse"),
        ("border", f"1px solid {color_with_alpha(accent_var, 0.04)}"),
    ]))
    if not source_styles.get("table"):
        extra_rules.append("table{" + table_style_text + "}")
    cell_style_text = declarations_text(_element_style("cell", [
        ("padding", "8px"), ("text-align", "left"),
    ]))
    if not source_styles.get("cell"):
        extra_rules.append("th,td{" + cell_style_text + "}")
    th_style_text = declarations_text(_element_style("th", [
        ("background-color", color_with_alpha(accent_var, 0.025)),
        ("color", coordinated_color(source_color_context, text_color, color_rng, fallback=text_color)),
    ]))
    if not source_styles.get("th"):
        extra_rules.append("th{" + th_style_text + "}")
    stripe_inline: tuple[tuple[str, str], ...] | None = None
    if source_styles.get("table_stripe") or (not source_styles.get("table") and maybe(rng, 0.3)):
        stripe_style_text = declarations_text(_element_style("table_stripe", [
            ("background-color", color_with_alpha(accent_var, 0.012)),
        ]))
        extra_rules.append("tbody tr:nth-child(even){" + stripe_style_text + "}")
        stripe_inline = _rules_to_inline(stripe_style_text)
    caption_inline: tuple[tuple[str, str], ...] | None = None
    if source_styles.get("caption") or (not source_styles.get("table") and maybe(rng, 0.2)):
        caption_style_text = declarations_text(_element_style("caption", [
            ("caption-side", "top"), ("color", accent_var), ("padding", "6px"),
        ]))
        extra_rules.append("table caption{" + caption_style_text + "}")
        caption_inline = _rules_to_inline(caption_style_text)

    button_style_text = declarations_text(_element_style("button", [
        ("background-color", accent_var),
        ("color", coordinated_color(source_color_context, _safe_text_for_bg(accent_var), color_rng, fallback=_safe_text_for_bg(accent_var))),
        ("border", "1px solid " + color_with_alpha(accent_var, 0.25)),
        ("padding", "8px 14px"), ("font-weight", "600"), ("cursor", "pointer"),
    ]))
    if not strict_mode and not source_styles.get("button"):
        button_style_text += f"border-radius:{rfloat(rng, 3.98, 4.02, 2)}px;"
    button_selector = "button,input[type=button],input[type=submit],input[type=reset]"
    if not source_styles.get("button"):
        extra_rules.append(button_selector + "{" + button_style_text + "}")


    small_style_text = declarations_text(_element_style("small", [
        ("color", coordinated_color(source_color_context, text_color, color_rng, fallback=text_color)),
        ("letter-spacing", "0.01em"),
    ]))
    if not source_styles.get("small"):
        extra_rules.append("small,sub,sup{" + small_style_text + "}")
    mark_style_text = declarations_text(_element_style("mark", [
        ("background-color", color_with_alpha(accent_var, 0.12)),
        ("color", coordinated_color(source_color_context, text_color, color_rng, fallback=text_color)),
        ("padding", "0 2px"),
    ]))
    if not source_styles.get("mark"):
        extra_rules.append("mark{" + mark_style_text + "}")
    abbr_style_text = declarations_text(_element_style("abbr", [
        ("border-bottom", "1px dotted " + accent_var),
        ("text-decoration-color", accent_var), ("cursor", "help"),
    ]))
    if not source_styles.get("abbr"):
        extra_rules.append("abbr{" + abbr_style_text + "}")
    cite_inline: tuple[tuple[str, str], ...] | None = None
    if source_styles.get("cite_em") or (not source_styles and maybe(rng, 0.2)):
        cite_style_text = declarations_text(_element_style("cite_em", [("color", accent_var)]))
        extra_rules.append("cite,em{" + cite_style_text + "}")
        cite_inline = _rules_to_inline(cite_style_text)


    def _inline_default(key: str, text: str):
        return None if source_styles.get(key) else _rules_to_inline(text)

    inline_styles = InlineStyleRules(
        headings=heading_inline, blockquote=quote_inline, code=code_inline,
        link=_inline_default("link", link_style_text),
        list_style=_inline_default("list", list_style_text),
        table=_inline_default("table", table_style_text),
        cell=_inline_default("cell", cell_style_text),
        th=_inline_default("th", th_style_text),
        table_stripe=stripe_inline, caption=caption_inline,
        button=_inline_default("button", button_style_text),
        small=_inline_default("small", small_style_text),
        mark=_inline_default("mark", mark_style_text),
        abbr=_inline_default("abbr", abbr_style_text), cite_em=cite_inline,
    )

    return body_css, wrapper_css, "".join(extra_rules), inline_styles


def letter_style(rng: random.Random, *, allow_inline_block: bool = True) -> str:
    fs = rfloat(rng, 0.998, 1.008, 4)
    ls = rfloat(rng, -0.008, 0.020, 4)
    op = 1.0

    # Keep text readable: no opacity, rotation, or baseline mutation.
    dy = 0.0

    display_rule = "display:inline;"
    if allow_inline_block and maybe(rng, 0.04):
        display_rule = "display:inline-block;vertical-align:middle;"

    whitespace_rule = ""

    font_variation = ""

    return (
        f"font-size:{fs}em;"
        "line-height:inherit;"
        f"letter-spacing:{ls}em;"
        f"opacity:{op};"
        f"{font_variation}"
        f"position:relative;top:{dy}px;"
        f"{display_rule}"
        f"{whitespace_rule}"
    )
