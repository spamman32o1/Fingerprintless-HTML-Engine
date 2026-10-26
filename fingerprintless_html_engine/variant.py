from __future__ import annotations

import hashlib
import html
import random
import re
import uuid
from collections import Counter

from .css_utils import (
    SourceColorContext,
    declarations_text,
    jitter_declarations,
    parse_color_value,
    parse_inline_style_declarations,
    prepare_source_colors,
    random_css,
)
from .image_utils import RemoteImageCache, inline_image_references
from .html_utils import extract_body_content_with_inline_safe_styles, minify_output_html
from .jsonld_utils import build_fake_jsonld_scripts
from .models import Opt
from .noise_utils import ie_noise_block, meta_noise
from .random_utils import _clamp_rate, maybe, pick, rfloat, rint
from .safe_css_utils import source_css_rules
from .structure_utils import randomize_structure, wrap_content_boxes
from .tag_utils import (
    _parse_tag_attrs,
    apply_inline_styles,
    is_strict_output_mode,
    normalize_input_html,
    replace_cellspacing_with_css,
)
from .text_utils import span_wrap_html


START_TAG_RE = re.compile(r"<([a-zA-Z0-9:_-]+)([^>]*)>", re.IGNORECASE)


def _extract_colors_from_attrs(
    attr_text: str,
    *,
    style_props: tuple[str, ...],
    legacy_attrs: tuple[str, ...],
) -> list[str]:
    style_colors: list[str] = []
    legacy_colors: list[str] = []
    attrs = _parse_tag_attrs(attr_text.strip())
    if not attrs and attr_text.strip():
        return []

    for attr_name, _raw, value in attrs:
        attr_lower = attr_name.lower()
        if attr_lower == "style" and value:
            style_map = parse_inline_style_declarations(value)
            for prop_name in style_props:
                parsed = parse_color_value(style_map.get(prop_name))
                if parsed:
                    style_colors.append(parsed)
        elif attr_lower in legacy_attrs:
            parsed = parse_color_value(value)
            if parsed:
                legacy_colors.append(parsed)
    return style_colors + legacy_colors


SOURCE_STYLE_KEYS = {
    "body": "body", "h1": "headings", "h2": "headings", "h3": "headings",
    "h4": "headings", "h5": "headings", "h6": "headings", "a": "link",
    "ul": "list", "ol": "list", "table": "table", "td": "cell", "th": "th",
    "button": "button", "input": "button", "small": "small", "sub": "small",
    "sup": "small", "mark": "mark", "abbr": "abbr", "cite": "cite_em",
    "em": "cite_em", "blockquote": "blockquote", "code": "code", "pre": "code",
}
COLOR_RE = re.compile(r"(?<![\w-])#[0-9a-fA-F]{3,8}\b|rgba?\([^()]+\)|hsla?\([^()]+\)")


def analyze_source_colors(content_html: str) -> SourceColorContext:
    body_text_colors: list[str] = []
    body_bg_colors: list[str] = []
    layout_text_colors: list[str] = []
    layout_bg_colors: list[str] = []
    repeated_text: Counter[str] = Counter()
    repeated_bg: Counter[str] = Counter()

    for selector, declarations in source_css_rules(content_html):
        if selector != "body":
            continue
        for name, value in declarations:
            if name == "color":
                if parsed := parse_color_value(value):
                    body_text_colors.append(parsed)
            elif name in {"background", "background-color"}:
                if parsed := parse_color_value(value):
                    body_bg_colors.append(parsed)

    for tag_name, attr_text in START_TAG_RE.findall(content_html):
        tag_name = tag_name.lower()
        text_colors = _extract_colors_from_attrs(
            attr_text,
            style_props=("color",),
            legacy_attrs=("text", "color"),
        )
        bg_colors = _extract_colors_from_attrs(
            attr_text,
            style_props=("background-color", "background"),
            legacy_attrs=("bgcolor",),
        )
        if tag_name == "body":
            body_text_colors.extend(text_colors)
            body_bg_colors.extend(bg_colors)
        if tag_name in {"table", "tbody", "tr", "td", "th"}:
            layout_text_colors.extend(text_colors)
            layout_bg_colors.extend(bg_colors)
        for color in text_colors:
            repeated_text[color] += 1
        for color in bg_colors:
            repeated_bg[color] += 1

    repeated_text_colors = [
        color for color, count in repeated_text.items() if count > 1
    ]
    repeated_bg_colors = [color for color, count in repeated_bg.items() if count > 1]
    return SourceColorContext(
        source_text_color=(
            body_text_colors or layout_text_colors or repeated_text_colors or [None]
        )[0],
        source_bg_color=(
            body_bg_colors or layout_bg_colors or repeated_bg_colors or [None]
        )[0],
        dominant_text_candidates=tuple(
            dict.fromkeys(body_text_colors + layout_text_colors + repeated_text_colors)
        ),
        dominant_bg_candidates=tuple(
            dict.fromkeys(body_bg_colors + layout_bg_colors + repeated_bg_colors)
        ),
    )


def analyze_source_styles(content_html: str, source_colors: SourceColorContext) -> SourceColorContext:
    """Collect source anchors; actual declarations remain on their original elements."""
    element_styles: dict[str, list[tuple[str, str]]] = {}
    body_styles: list[tuple[str, str]] = []
    colors: list[str] = []

    def capture(key: str, declarations: tuple[tuple[str, str], ...]) -> None:
        target = element_styles.setdefault(key, [])
        target.extend(declarations)
        for name, value in declarations:
            if name in {"color", "border-color", "text-decoration-color", "outline-color"}:
                colors.extend(COLOR_RE.findall(value))

    for selector, declarations in source_css_rules(content_html):
        key = SOURCE_STYLE_KEYS.get(selector)
        if key:
            capture(key, declarations)
        if selector == "body":
            body_styles.extend(declarations)

    for tag_name, attr_text in START_TAG_RE.findall(content_html):
        tag_name = tag_name.lower()
        attrs = _parse_tag_attrs(attr_text.strip())
        declarations = parse_inline_style_declarations(next(
            (value or "" for name, _, value in attrs if name.lower() == "style"), ""
        ))
        styles = list(declarations.items())
        for name, _raw, value in attrs:
            if value is None:
                continue
            name = name.lower()
            prop = {"color": "color", "text": "color", "bgcolor": "background-color", "face": "font-family"}.get(name)
            if prop and prop not in declarations:
                styles.append((prop, value))
        if tag_name == "body":
            body_styles.extend(styles)
        elif tag_name in SOURCE_STYLE_KEYS:
            capture(SOURCE_STYLE_KEYS[tag_name], tuple(styles))
        for name, value in styles:
            if name in {"color", "border-color", "text-decoration-color", "outline-color"}:
                colors.extend(COLOR_RE.findall(value))

    body_declarations = tuple(dict(body_styles).items())

    def source_gradients(value: str) -> tuple[str, ...]:
        found: list[str] = []
        for match in re.finditer(r"(?i)(?:repeating-)?(?:linear|radial)-gradient\(", value):
            depth = 0
            for index in range(match.start(), len(value)):
                if value[index] == "(":
                    depth += 1
                elif value[index] == ")":
                    depth -= 1
                    if depth == 0:
                        found.append(value[match.start():index + 1])
                        break
        return tuple(found)

    gradients = tuple(
        gradient
        for name, value in body_declarations
        if name in {"background", "background-image"}
        for gradient in source_gradients(value)
    )
    overlays = tuple(gradient for gradient in gradients if gradient.lower().startswith("repeating-"))
    return SourceColorContext(
        source_text_color=source_colors.source_text_color,
        source_bg_color=source_colors.source_bg_color,
        dominant_text_candidates=source_colors.dominant_text_candidates,
        dominant_bg_candidates=source_colors.dominant_bg_candidates,
        accent_candidates=tuple(dict.fromkeys(colors)),
        gradient_candidates=gradients,
        overlay_candidates=overlays,
        body_styles=body_declarations,
        has_source_styles=bool(body_styles or element_styles),
        element_styles=tuple((key, tuple(dict(styles).items())) for key, styles in element_styles.items()),
    )


def randomize_opt_for_variant(rng: random.Random, opt: Opt) -> Opt:
    wrap_factor = rfloat(rng, 0.8, 1.2)
    word_factor = rfloat(rng, 0.8, 1.2)

    chunk_len_min = max(1, opt.chunk_len_min + rint(rng, -1, 1))
    chunk_len_max = max(chunk_len_min, opt.chunk_len_max + rint(rng, -1, 1))

    noise_divs_max = max(0, opt.noise_divs_max + rint(rng, -1, 1))
    nesting_jitter = max(0, opt.max_nesting_jitter)
    max_nesting = max(1, opt.max_nesting + rint(rng, -nesting_jitter, nesting_jitter))

    return Opt(
        count=opt.count,
        wrap_chunk_rate=_clamp_rate(opt.wrap_chunk_rate * wrap_factor),
        chunk_len_min=chunk_len_min,
        chunk_len_max=chunk_len_max,
        per_word_rate=_clamp_rate(opt.per_word_rate * word_factor),
        enable_wrap_chunk_rate=opt.enable_wrap_chunk_rate,
        enable_per_word_rate=opt.enable_per_word_rate,
        noise_divs_max=noise_divs_max,
        max_nesting=max_nesting,
        max_nesting_jitter=opt.max_nesting_jitter,
        title_prefix=opt.title_prefix,
        ie_condition_randomize=opt.ie_condition_randomize,
        structure_randomize=opt.structure_randomize,
        output_mode=opt.output_mode,
        allow_dark_mode=opt.allow_dark_mode,
        enable_css_randomization=opt.enable_css_randomization,
        enable_font_css=opt.enable_font_css,
        enable_font_randomization=opt.enable_font_randomization,
        enable_font_features=opt.enable_font_features,
        enable_gradients=opt.enable_gradients,
        enable_noise_textures=opt.enable_noise_textures,
        enable_color_palette_randomization=opt.enable_color_palette_randomization,
        enable_span_wrapping=opt.enable_span_wrapping,
        enable_meta_noise=opt.enable_meta_noise,
        enable_jsonld_noise=opt.enable_jsonld_noise,
        enable_noise_divs=opt.enable_noise_divs,
        enable_wrapper_nesting=opt.enable_wrapper_nesting,
        enable_layout_randomization=opt.enable_layout_randomization,
        enable_body_styles=opt.enable_body_styles,
        enable_image_inlining=opt.enable_image_inlining,
        enable_remote_image_cache=opt.enable_remote_image_cache,
        disable_layout_tables=opt.disable_layout_tables,
        disable_wrapper_styles=opt.disable_wrapper_styles,
        pretty_output=opt.pretty_output,
    )


def random_title() -> str:
    return f"letter-{uuid.uuid4().hex[:12]}"


def _variant_identity(idx: int, title: str) -> str:
    # Include index and title so direct API callers also receive distinct documents.
    return hashlib.sha256(f"{idx}:{title}".encode("utf-8")).hexdigest()[:24]


def build_variant(
    rng: random.Random,
    content_html: str,
    opt: Opt,
    idx: int,
    lang: str,
    title: str,
    synonym_patterns=None,
    image_cache: RemoteImageCache | None = None,
) -> str:
    if synonym_patterns is None:
        synonym_patterns = []
    opt = randomize_opt_for_variant(rng, opt)
    strict_mode = is_strict_output_mode(opt.output_mode)
    super_strict = opt.output_mode in {"super_strict", "libero"}
    content_html = normalize_input_html(content_html, strict_mode=strict_mode)
    source_color_context = analyze_source_colors(content_html)
    source_color_context = analyze_source_styles(content_html, source_color_context)
    original_body_declarations: list[tuple[str, str]] = list(source_color_context.body_styles)
    body_attributes = ""
    body_match = re.search(r"(?is)<body\b([^>]*)>", content_html)
    if body_match:
        retained_attributes: list[str] = []
        body_declaration_names = {name for name, _ in original_body_declarations}
        legacy_body_declarations: list[tuple[str, str]] = []
        for attr_name, raw, value in _parse_tag_attrs(body_match.group(1).strip()):
            attr_name = attr_name.lower()
            if attr_name == "style":
                declarations = parse_inline_style_declarations(value)
                original_body_declarations.extend(declarations.items())
                body_declaration_names.update(declarations)
            elif attr_name in {"text", "bgcolor", "background"} and value:
                legacy_body_declarations.append((
                    "background-color" if attr_name == "bgcolor" else ("background" if attr_name == "background" else "color"),
                    value,
                ))
            else:
                retained_attributes.append(raw)
        original_body_declarations.extend(
            (name, value) for name, value in legacy_body_declarations
            if name not in body_declaration_names
        )
        body_attributes = " ".join(retained_attributes)
    color_variants: dict[str, str] = {}
    source_color_context = prepare_source_colors(
        source_color_context,
        rng,
        enabled=opt.enable_color_palette_randomization,
        color_variants=color_variants,
    )

    def jitter_source_declarations(declarations):
        return jitter_declarations(
            declarations,
            rng,
            enabled=opt.enable_css_randomization,
            color_enabled=opt.enable_color_palette_randomization,
            source_color_context=source_color_context,
            color_variants=color_variants,
        )

    content_html = extract_body_content_with_inline_safe_styles(
        content_html,
        strict_mode=strict_mode,
        jitter=jitter_source_declarations,
    )
    content_html = inline_image_references(
        content_html,
        enabled=opt.enable_image_inlining and opt.output_mode != "libero",
        cache=(
            image_cache
            if opt.enable_remote_image_cache
            else RemoteImageCache(enabled=False)
        ),
    )
    content_html = replace_cellspacing_with_css(content_html)
    body_css, wrapper_css, extra_css, inline_styles = random_css(
        rng,
        opt.output_mode,
        allow_dark_mode=opt.allow_dark_mode,
        enable_css_randomization=opt.enable_css_randomization,
        enable_font_css=opt.enable_font_css,
        enable_font_randomization=opt.enable_font_randomization,
        enable_font_features=opt.enable_font_features,
        enable_gradients=opt.enable_gradients,
        enable_noise_textures=opt.enable_noise_textures,
        enable_color_palette_randomization=opt.enable_color_palette_randomization,
        enable_body_styles=opt.enable_body_styles,
        source_color_context=source_color_context,
    )
    if original_body_declarations:
        body_css = (
            declarations_text(jitter_source_declarations(original_body_declarations))
            if opt.enable_body_styles
            else ""
        )
    if opt.disable_wrapper_styles:
        wrapper_css = ""
    wrapper_class = f"{uuid.uuid4().hex[:6]}"
    content_class = f"{uuid.uuid4().hex[:6]}"

    structured_html = (
        content_html
        if super_strict
        else randomize_structure(rng, content_html, opt.structure_randomize)
    )
    inner = span_wrap_html(
        rng,
        structured_html,
        opt,
        synonym_patterns,
        inline_styles=inline_styles if strict_mode else None,
        wrap_spans=not strict_mode and opt.enable_span_wrapping,
        output_mode=opt.output_mode,
    )
    jsonld_scripts = (
        ""
        if super_strict or not opt.enable_jsonld_noise
        else build_fake_jsonld_scripts(rng)
    )

    before = ""
    after = ""
    if opt.ie_condition_randomize and not super_strict:
        before += ie_noise_block(rng, True)
        after += ie_noise_block(rng, True)

    depth = (
        0
        if super_strict or not opt.enable_wrapper_nesting
        else rint(rng, 1, max(1, opt.max_nesting))
    )
    open_wrap = ""
    close_wrap = ""
    for _ in range(depth):
        pad = rfloat(rng, 0.0, 0.1, 3)
        mt = rfloat(rng, 0.0, 0.1, 3)
        mb = rfloat(rng, 0.0, 0.1, 3)
        disp = pick(rng, ["block", "flow-root"])
        nested_class = f"{uuid.uuid4().hex[:9]}"
        open_wrap += (
            f'<div class="{nested_class}" '
            f'style="padding:{pad}px;margin:{mt}px 0 {mb}px 0;display:{disp};">'
        )
        close_wrap = "</div>" + close_wrap

    rendered = build_layout_template(
        rng=rng,
        lang=lang,
        title=title,
        inner=inner,
        wrapper_class=wrapper_class,
        content_class=content_class,
        before=before,
        after=after,
        open_wrap=open_wrap,
        close_wrap=close_wrap,
        body_css=body_css,
        wrapper_css=wrapper_css,
        jsonld_scripts=jsonld_scripts,
        extra_css=extra_css,
        output_mode=opt.output_mode,
        variant_identity=_variant_identity(idx, title),
        allow_ie_conditional_comments=opt.ie_condition_randomize,
        enable_meta_noise=opt.enable_meta_noise,
        enable_layout_randomization=opt.enable_layout_randomization,
        disable_layout_tables=opt.disable_layout_tables,
        disable_wrapper_styles=opt.disable_wrapper_styles,
        body_attributes=body_attributes,
        table_css="table.layout-table,table.inner-table{width:100%;border-collapse:collapse;}",
        source_bg_color=source_color_context.source_bg_color,
        has_source_body_styles=bool(original_body_declarations),
    )
    return minify_output_html(rendered, pretty_output=opt.pretty_output)


def build_layout_template(
    rng: random.Random,
    lang: str,
    title: str,
    inner: str,
    wrapper_class: str,
    content_class: str,
    before: str,
    after: str,
    open_wrap: str,
    close_wrap: str,
    body_css: str,
    wrapper_css: str,
    jsonld_scripts: str,
    extra_css: str,
    output_mode: str,
    allow_ie_conditional_comments: bool = True,
    enable_meta_noise: bool = False,
    enable_layout_randomization: bool = True,
    disable_layout_tables: bool = False,
    disable_wrapper_styles: bool = False,
    body_attributes: str = "",
    table_css: str = "",
    source_bg_color: str | None = None,
    has_source_body_styles: bool = False,
    variant_identity: str = "",
) -> str:
    strict_mode = is_strict_output_mode(output_mode)
    super_strict = output_mode in {"super_strict", "libero"}
    body_background_color = source_bg_color or parse_color_value(
        parse_inline_style_declarations(body_css).get("background-color")
        or parse_inline_style_declarations(body_css).get("background")
    )
    body_style_attr = (
        f' style="{html.escape(body_css, quote=True)}"'
        if body_css and strict_mode
        else ""
    )
    if strict_mode and not disable_wrapper_styles and wrapper_css:
        wrapper_style_attr = f' style="{html.escape(wrapper_css, quote=True)}"'
    else:
        wrapper_style_attr = ""
    wrapper_class_attr = f' class="{wrapper_class}"' if not strict_mode else ""
    content_class_attr = f' class="{content_class}"' if not strict_mode else ""
    if strict_mode:
        style_block = ""
    else:
        body_rule = (
            table_css
            + (f"body{{{body_css}}}" if body_css and not has_source_body_styles else "")
        )
        style_block = (
            "<style>"
            f"{body_rule}"
            f".{wrapper_class}{{{wrapper_css}}}"
            f"{extra_css}"
            "</style>"
        )
    head_html = (
        "<!doctype html>"
        f'<html lang="{html.escape(lang, quote=True)}">'
        "<head>"
        '<meta charset="utf-8" />'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />'
        '<meta name="x-apple-disable-message-reformatting" content="yes" />'
        f"{meta_noise(rng, enabled=enable_meta_noise, source_bg_color=body_background_color) if not strict_mode else ''}"
        f"<title>{html.escape(title)}</title>"
        f"{style_block}"
        f"{jsonld_scripts}"
        "</head>"
    )

    outer_table_class = "" if strict_mode else ' class="layout-table"'
    outer_table_open = (
        f'<table role="presentation"{outer_table_class} '
        'style="width:100%;border-collapse:collapse;border-spacing:0;">'
        "<tr><td>"
    )
    outer_table_close = "</td></tr></table>"
    inner_table_class = "" if strict_mode else ' class="inner-table"'
    inner_table_open = (
        f'<table role="presentation"{inner_table_class} '
        'style="width:100%;border-collapse:collapse;border-spacing:0;">'
        "<tr><td>"
    )
    inner_table_close = "</td></tr></table>"

    table_fallback_open = ""
    table_fallback_close = ""
    if allow_ie_conditional_comments:
        table_fallback_open = (
            '<!--[if (mso)|(IE)]><table role="presentation" width="100%" '
            'style="border-collapse:collapse;border-spacing:0;"><tr><td><![endif]-->'
        )
        table_fallback_close = "<!--[if (mso)|(IE)]></td></tr></table><![endif]-->"

    if super_strict or not enable_layout_randomization:
        placement = "inner"
    else:
        placement = pick(
            rng,
            ["inner", "body-outside", "mixed-before", "mixed-after"],
        )
    before_body = ""
    after_body = ""
    before_inner = ""
    after_inner = ""
    if placement == "inner":
        before_inner = before
        after_inner = after
    elif placement == "body-outside":
        before_body = before
        after_body = after
    elif placement == "mixed-before":
        before_body = before
        after_inner = after
    else:
        before_inner = before
        after_body = after

    inner_html = wrap_content_boxes(inner) if not strict_mode else inner
    content_inner = f"{open_wrap}{before_inner}<div{content_class_attr}>{inner_html}</div>{after_inner}{close_wrap}"

    def build_wrapper(content_html: str) -> str:
        wrapper_open = f"<div{wrapper_class_attr}{wrapper_style_attr}>"
        wrapper_close = "</div>"
        if not super_strict and maybe(rng, 0.45):
            wrap_tag = pick(rng, ["section", "div"])
            role = ""
            if wrap_tag == "div" and maybe(rng, 0.5):
                role = ' role="presentation"'
            wrapper_open += f"<{wrap_tag}{role}>"
            wrapper_close = f"</{wrap_tag}>{wrapper_close}"
        return f"{wrapper_open}{content_html}{wrapper_close}"

    use_outer_layer = False if super_strict else maybe(rng, 0.35)
    outer_layer_open = ""
    outer_layer_close = ""
    if use_outer_layer:
        outer_tag = pick(rng, ["section", "div"])
        role = ""
        if outer_tag == "div" and maybe(rng, 0.5):
            role = ' role="presentation"'
        outer_layer_open = f"<{outer_tag}{role}>"
        outer_layer_close = f"</{outer_tag}>"

    if disable_layout_tables:
        layout_choice = "plain"
    elif super_strict:
        layout_choice = "outer-table-fallback"
    elif not enable_layout_randomization:
        layout_choice = "plain"
    else:
        layout_choice = pick(
            rng,
            [
                "outer-table",
                "outer-table-fallback",
                "outer-table-inner",
                "inner-only",
                "plain",
            ],
        )
    use_outer_table = layout_choice in {
        "outer-table",
        "outer-table-fallback",
        "outer-table-inner",
    }
    use_inner_table = layout_choice in {"outer-table-inner", "inner-only"}
    use_commented_table = (
        layout_choice == "outer-table-fallback" and allow_ie_conditional_comments
    )

    wrapper_default = build_wrapper(content_inner)
    body_inner = wrapper_default
    if use_inner_table:
        body_inner = f"{inner_table_open}{body_inner}{inner_table_close}"

    outer_container = f"{outer_layer_open}{body_inner}{outer_layer_close}"
    if use_outer_table:
        outer_container = f"{outer_table_open}{outer_container}{outer_table_close}"
        if use_commented_table:
            outer_container = (
                f"{table_fallback_open}{outer_container}{table_fallback_close}"
            )

    identity_attribute = ""
    if variant_identity:
        identity_name = f"data-x{variant_identity[:8]}"
        if not re.search(rf"(?i)\b{re.escape(identity_name)}\s*=", body_attributes):
            identity_attribute = f' {identity_name}="{html.escape(variant_identity, quote=True)}"'
    body_attr_text = (" " + body_attributes) if body_attributes else ""
    return f"{head_html}<body{body_style_attr}{identity_attribute}{body_attr_text}>{before_body}{outer_container}{after_body}</body></html>"
