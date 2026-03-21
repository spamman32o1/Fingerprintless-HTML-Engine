from __future__ import annotations

import html
import random
import re
import uuid
from collections import Counter

from .css_utils import SourceColorContext, parse_color_value, parse_inline_style_declarations, random_css
from .image_utils import RemoteImageCache, inline_image_references
from .html_utils import minify_output_html
from .jsonld_utils import build_fake_jsonld_scripts
from .models import Opt
from .noise_utils import ie_noise_block, meta_noise, noise_divs
from .random_utils import _clamp_rate, maybe, pick, rfloat, rint
from .structure_utils import randomize_structure, wrap_content_boxes
from .tag_utils import _parse_tag_attrs, is_strict_output_mode, normalize_input_html, replace_cellspacing_with_css
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


def analyze_source_colors(content_html: str) -> SourceColorContext:
    body_text_colors: list[str] = []
    body_bg_colors: list[str] = []
    layout_text_colors: list[str] = []
    layout_bg_colors: list[str] = []
    repeated_text: Counter[str] = Counter()
    repeated_bg: Counter[str] = Counter()

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

    repeated_text_colors = [color for color, count in repeated_text.items() if count > 1]
    repeated_bg_colors = [color for color, count in repeated_bg.items() if count > 1]
    return SourceColorContext(
        source_text_color=(body_text_colors or layout_text_colors or repeated_text_colors or [None])[0],
        source_bg_color=(body_bg_colors or layout_bg_colors or repeated_bg_colors or [None])[0],
        dominant_text_candidates=tuple(
            dict.fromkeys(body_text_colors + layout_text_colors + repeated_text_colors)
        ),
        dominant_bg_candidates=tuple(
            dict.fromkeys(body_bg_colors + layout_bg_colors + repeated_bg_colors)
        ),
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
        enable_alt_text_randomization=opt.enable_alt_text_randomization,
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
    content_html = inline_image_references(
        content_html,
        enabled=opt.enable_image_inlining,
        cache=(image_cache if opt.enable_remote_image_cache else RemoteImageCache(enabled=False)),
    )
    source_color_context = analyze_source_colors(content_html)
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
    if opt.disable_wrapper_styles:
        wrapper_css = ""
    wrapper_class = f"{uuid.uuid4().hex[:6]}"
    content_class = f"{uuid.uuid4().hex[:6]}"
    structured_html = (
        content_html if super_strict else randomize_structure(rng, content_html, opt.structure_randomize)
    )
    inner = span_wrap_html(
        rng,
        structured_html,
        opt,
        synonym_patterns,
        inline_styles=inline_styles if strict_mode else None,
        wrap_spans=not strict_mode and opt.enable_span_wrapping,
    )
    jsonld_scripts = (
        ""
        if super_strict or not opt.enable_jsonld_noise
        else build_fake_jsonld_scripts(rng)
    )

    if not super_strict:
        ie_before = ie_noise_block(rng, opt.ie_condition_randomize)
        ie_after = ie_noise_block(rng, opt.ie_condition_randomize)
        if strict_mode:
            before = ie_before
            after = ie_after
        else:
            before = ie_before + noise_divs(
                rng,
                opt.noise_divs_max,
                enabled=opt.enable_noise_divs,
            )
            after = noise_divs(
                rng,
                opt.noise_divs_max,
                enabled=opt.enable_noise_divs,
            ) + ie_after
    else:
        ie_before = ""
        ie_after = ""
        before = ""
        after = ""

    depth = (
        0
        if super_strict or not opt.enable_wrapper_nesting
        else rint(rng, 1, max(1, opt.max_nesting))
    )
    open_wrap = ""
    close_wrap = ""
    for _ in range(depth):
        pad = rfloat(rng, 0.0, 12.0, 2)
        mt = rfloat(rng, 0.0, 10.0, 2)
        mb = rfloat(rng, 0.0, 10.0, 2)
        disp = pick(rng, ["block", "flow-root", "contents"])
        nested_class = f"{uuid.uuid4().hex[:9]}"
        open_wrap += (
            f'<div class="{nested_class}" '
            f"style=\"padding:{pad}px;margin:{mt}px 0 {mb}px 0;display:{disp};\">"
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
        allow_ie_conditional_comments=opt.ie_condition_randomize,
        enable_meta_noise=opt.enable_meta_noise,
        enable_layout_randomization=opt.enable_layout_randomization,
        disable_layout_tables=opt.disable_layout_tables,
        disable_wrapper_styles=opt.disable_wrapper_styles,
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
    enable_meta_noise: bool = True,
    enable_layout_randomization: bool = True,
    disable_layout_tables: bool = False,
    disable_wrapper_styles: bool = False,
) -> str:
    strict_mode = is_strict_output_mode(output_mode)
    super_strict = output_mode in {"super_strict", "libero"}
    body_style_attr = (
        f' style="{html.escape(body_css, quote=True)}"' if strict_mode and body_css else ""
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
        body_rule = f"body{{{body_css}}}" if body_css else ""
        style_block = (
            "<style>"
            f"{body_rule}"
            f".{wrapper_class}{{{wrapper_css}}}"
            f"{extra_css}"
            "</style>"
        )
    head_html = (
        "<!doctype html>"
        f"<html lang=\"{html.escape(lang, quote=True)}\">"
        "<head>"
        "<meta charset=\"utf-8\" />"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />"
        "<meta name=\"x-apple-disable-message-reformatting\" content=\"yes\" />"
        f"{meta_noise(rng, enabled=enable_meta_noise) if not strict_mode else ''}"
        f"<title>{html.escape(title)}</title>"
        f"{style_block}"
        f"{jsonld_scripts}"
        "</head>"
    )

    outer_table_class = '' if strict_mode else ' class="layout-table"'
    outer_table_open = (
        f'<table role="presentation"{outer_table_class} '
        "style=\"width:100%;border-collapse:collapse;border-spacing:0;\">"
        "<tr><td>"
    )
    outer_table_close = "</td></tr></table>"
    inner_table_class = '' if strict_mode else ' class="inner-table"'
    inner_table_open = (
        f'<table role="presentation"{inner_table_class} '
        "style=\"width:100%;border-collapse:collapse;border-spacing:0;\">"
        "<tr><td>"
    )
    inner_table_close = "</td></tr></table>"

    table_fallback_open = ""
    table_fallback_close = ""
    if allow_ie_conditional_comments:
        table_fallback_open = (
            "<!--[if (mso)|(IE)]><table role=\"presentation\" width=\"100%\" "
            "style=\"border-collapse:collapse;border-spacing:0;\"><tr><td><![endif]-->"
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
    content_inner = (
        f"{open_wrap}{before_inner}<div{content_class_attr}>{inner_html}</div>{after_inner}{close_wrap}"
    )

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
    use_outer_table = layout_choice in {"outer-table", "outer-table-fallback", "outer-table-inner"}
    use_inner_table = layout_choice in {"outer-table-inner", "inner-only"}
    use_commented_table = layout_choice == "outer-table-fallback" and allow_ie_conditional_comments

    wrapper_default = build_wrapper(content_inner)
    body_inner = wrapper_default
    if use_inner_table:
        body_inner = f"{inner_table_open}{body_inner}{inner_table_close}"

    outer_container = f"{outer_layer_open}{body_inner}{outer_layer_close}"
    if use_outer_table:
        outer_container = f"{outer_table_open}{outer_container}{outer_table_close}"
        if use_commented_table:
            outer_container = f"{table_fallback_open}{outer_container}{table_fallback_close}"

    return f"{head_html}<body{body_style_attr}>{before_body}{outer_container}{after_body}</body></html>"
