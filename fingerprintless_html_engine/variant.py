from __future__ import annotations

import html
import random
import uuid

from .css_utils import random_css
from .html_utils import minify_output_html
from .jsonld_utils import build_fake_jsonld_scripts
from .models import Opt
from .noise_utils import ie_noise_block, meta_noise, noise_divs
from .random_utils import _clamp_rate, maybe, pick, rfloat, rint
from .structure_utils import randomize_structure
from .tag_utils import normalize_input_html, replace_cellspacing_with_css
from .text_utils import span_wrap_html


def randomize_opt_for_variant(rng: random.Random, opt: Opt) -> Opt:
    wrap_factor = rfloat(rng, 0.8, 1.2)
    word_factor = rfloat(rng, 0.8, 1.2)

    chunk_len_min = max(1, opt.chunk_len_min + rint(rng, -1, 1))
    chunk_len_max = max(chunk_len_min, opt.chunk_len_max + rint(rng, -1, 1))

    noise_divs_max = max(0, opt.noise_divs_max + rint(rng, -1, 1))
    meta_noise_min = max(0, opt.meta_noise_min + rint(rng, -2, 2))
    meta_noise_max = max(meta_noise_min, opt.meta_noise_max + rint(rng, -2, 2))

    return Opt(
        count=opt.count,
        wrap_chunk_rate=_clamp_rate(opt.wrap_chunk_rate * wrap_factor),
        chunk_len_min=chunk_len_min,
        chunk_len_max=chunk_len_max,
        per_word_rate=_clamp_rate(opt.per_word_rate * word_factor),
        noise_divs_max=noise_divs_max,
        max_nesting=opt.max_nesting,
        title_prefix=opt.title_prefix,
        meta_noise_min=meta_noise_min,
        meta_noise_max=meta_noise_max,
        ie_condition_randomize=opt.ie_condition_randomize,
        structure_randomize=opt.structure_randomize,
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
) -> str:
    if synonym_patterns is None:
        synonym_patterns = []
    opt = randomize_opt_for_variant(rng, opt)
    content_html = normalize_input_html(content_html)
    content_html = replace_cellspacing_with_css(content_html)
    body_css, wrapper_css, extra_css = random_css(rng)
    wrapper_class = f"{uuid.uuid4().hex[:6]}"
    content_class = f"{uuid.uuid4().hex[:6]}"
    structured_html = randomize_structure(rng, content_html, opt.structure_randomize)
    inner = span_wrap_html(rng, structured_html, opt, synonym_patterns)
    jsonld_scripts = build_fake_jsonld_scripts(rng)
    meta_noise_html = meta_noise(rng, opt.meta_noise_min, opt.meta_noise_max)

    ie_before = ie_noise_block(rng, opt.ie_condition_randomize)
    ie_after = ie_noise_block(rng, opt.ie_condition_randomize)

    before = ie_before + noise_divs(rng, opt.noise_divs_max)
    after = noise_divs(rng, opt.noise_divs_max) + ie_after

    depth = rint(rng, 1, max(1, opt.max_nesting))
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
        meta_noise_html=meta_noise_html,
    )
    return minify_output_html(rendered)


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
    meta_noise_html: str,
) -> str:
    head_html = (
        "<!doctype html>"
        f"<html lang=\"{html.escape(lang, quote=True)}\">"
        "<head>"
        "<meta charset=\"utf-8\" />"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />"
        "<meta name=\"x-apple-disable-message-reformatting\" content=\"yes\" />"
        f"{meta_noise_html}"
        f"<title>{html.escape(title)}</title>"
        "<style>"
        f"body{{{body_css}}}"
        f".{wrapper_class}{{{wrapper_css}}}"
        f"{extra_css}"
        "</style>"
        f"{jsonld_scripts}"
        "</head>"
    )

    outer_table_open = (
        '<table role="presentation" class="layout-table" '
        "style=\"width:100%;border-collapse:collapse;border-spacing:0;\">"
        "<tr><td>"
    )
    outer_table_close = "</td></tr></table>"
    inner_table_open = (
        '<table role="presentation" class="inner-table" '
        "style=\"width:100%;border-collapse:collapse;border-spacing:0;\">"
        "<tr><td>"
    )
    inner_table_close = "</td></tr></table>"

    table_fallback_open = (
        "<!--[if (mso)|(IE)]><table role=\"presentation\" width=\"100%\" "
        "style=\"border-collapse:collapse;border-spacing:0;\"><tr><td><![endif]-->"
    )
    table_fallback_close = "<!--[if (mso)|(IE)]></td></tr></table><![endif]-->"

    placement = pick(rng, ["inner", "body-outside", "mixed-before", "mixed-after"])
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

    content_inner = f"{open_wrap}{before_inner}<div class=\"{content_class}\">{inner}</div>{after_inner}{close_wrap}"

    def build_wrapper(content_html: str) -> str:
        wrapper_open = f"<div class=\"{wrapper_class}\">"
        wrapper_close = "</div>"
        if maybe(rng, 0.45):
            wrap_tag = pick(rng, ["section", "div"])
            role = ""
            if wrap_tag == "div" and maybe(rng, 0.5):
                role = ' role="presentation"'
            wrapper_open += f"<{wrap_tag}{role}>"
            wrapper_close = f"</{wrap_tag}>{wrapper_close}"
        return f"{wrapper_open}{content_html}{wrapper_close}"

    outer_layer_open = ""
    outer_layer_close = ""
    if maybe(rng, 0.35):
        outer_tag = pick(rng, ["section", "div"])
        role = ""
        if outer_tag == "div" and maybe(rng, 0.5):
            role = ' role="presentation"'
        outer_layer_open = f"<{outer_tag}{role}>"
        outer_layer_close = f"</{outer_tag}>"

    wrapper_default = build_wrapper(content_inner)
    wrapper_with_inner_table = build_wrapper(f"{inner_table_open}{content_inner}{inner_table_close}")
    wrapper_with_commented_table = build_wrapper(
        f"{table_fallback_open}{inner_table_open}{content_inner}{inner_table_close}{table_fallback_close}"
    )

    templates = [
        lambda: (
            f"{head_html}<body>{before_body}{outer_table_open}{table_fallback_open}"
            f"{outer_layer_open}{wrapper_default}{outer_layer_close}{table_fallback_close}"
            f"{outer_table_close}{after_body}</body></html>"
        ),
        lambda: (
            f"{head_html}<body>{before_body}{outer_layer_open}{wrapper_default}"
            f"{outer_layer_close}{after_body}</body></html>"
        ),
        lambda: (
            f"{head_html}<body>{before_body}{outer_table_open}{outer_layer_open}"
            f"{wrapper_with_inner_table}{outer_layer_close}{outer_table_close}{after_body}</body></html>"
        ),
        lambda: (
            f"{head_html}<body>{before_body}{outer_layer_open}{wrapper_with_commented_table}"
            f"{outer_layer_close}{after_body}</body></html>"
        ),
        lambda: (
            f"{head_html}<body>{before_body}{table_fallback_open}{outer_table_open}{outer_layer_open}"
            f"{wrapper_default}{outer_layer_close}{outer_table_close}{table_fallback_close}"
            f"{after_body}</body></html>"
        ),
    ]

    return pick(rng, templates)()
