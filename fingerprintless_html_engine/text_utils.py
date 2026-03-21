from __future__ import annotations

import html
import random
import re
import string
from typing import List, Tuple

from .constants import ENTITY_RE, SKIP_TEXT_INSIDE, TAG_SPLIT_RE, TEMPLATE_SPLIT_RE
from .css_utils import InlineStyleRules, letter_style
from .models import Opt
from .random_utils import maybe, pick, rint
from .tag_utils import (
    _parse_tag_attrs,
    _update_attr_value,
    apply_inline_styles,
    is_strict_output_mode,
    normalize_table_cellspacing,
    reorder_tag_attributes,
)


def parse_synonym_lines(lines: List[str]) -> List[List[str]]:
    groups: List[List[str]] = []
    for line in lines:
        parts = [part.strip() for part in line.split("|") if part.strip()]
        if len(parts) >= 2:
            groups.append(parts)
    return groups


def build_synonym_patterns(
    groups: List[List[str]],
) -> List[Tuple[re.Pattern, List[str]]]:
    patterns: List[Tuple[re.Pattern, List[str]]] = []
    for group in groups:
        escaped = sorted((re.escape(word) for word in group), key=len, reverse=True)
        if not escaped:
            continue
        pattern = re.compile(rf"(?i)(?<!\w)(?:{'|'.join(escaped)})(?!\w)")
        patterns.append((pattern, group))
    return patterns


def apply_synonyms(
    text: str, rng: random.Random, patterns: List[Tuple[re.Pattern, List[str]]]
) -> str:
    if not patterns:
        return text

    def apply_casing(match_text: str, replacement: str) -> str:
        if match_text.isupper():
            return replacement.upper()
        if match_text.islower():
            return replacement.lower()
        if match_text.istitle():
            return replacement.title()
        return replacement

    updated = text
    for pattern, options in patterns:
        updated = pattern.sub(
            lambda match: apply_casing(match.group(0), pick(rng, options)),
            updated,
        )
    return updated


def normalize_text_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def tokenize_text_preserving_entities(text: str) -> List[tuple[str, str]]:
    tokens: List[tuple[str, str]] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i].isspace():
            j = i + 1
            while j < n and text[j].isspace():
                j += 1
            tokens.append(("ws", text[i:j]))
            i = j
            continue

        m = ENTITY_RE.match(text, i)
        if m:
            tokens.append(("entity", m.group(0)))
            i = m.end()
            continue

        tokens.append(("char", text[i]))
        i += 1

    return tokens


def _extract_px_style_value(style_value: str | None, prop: str) -> str | None:
    if not style_value:
        return None
    match = re.search(
        rf"{re.escape(prop)}\s*:\s*([0-9]+(?:\.[0-9]+)?)px", style_value, re.IGNORECASE
    )
    if not match:
        return None
    value = match.group(1)
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    return value or "0"


def _add_attr_if_missing(tag: str, attr_name: str, attr_value: str) -> str:
    if (
        not tag.startswith("<")
        or tag.startswith("</")
        or tag.startswith("<!")
        or tag.startswith("<?")
    ):
        return tag

    m = re.match(r"^<\s*([a-zA-Z0-9:_-]+)([^>]*)>$", tag)
    if not m:
        return tag

    name, rest = m.group(1), m.group(2)
    trailing_slash = rest.rstrip().endswith("/")
    rest = rest.rstrip().rstrip("/")
    attrs = _parse_tag_attrs(rest.strip())
    if not attrs and rest.strip():
        return tag

    if any(parsed_name.lower() == attr_name.lower() for parsed_name, _, _ in attrs):
        return tag

    updated_attrs = [raw for _, raw, _ in attrs]
    updated_attrs.append(f'{attr_name}="{attr_value}"')

    attr_str = " ".join(updated_attrs).strip()
    slash = " /" if trailing_slash else ""
    if attr_str:
        return f"<{name} {attr_str}{slash}>"
    return f"<{name}{slash}>"


_STYLE_PROP_RE = re.compile(r"([a-zA-Z-]+)\s*:\s*([^;]+)")


def _parse_style_props(style_value: str | None) -> dict[str, str]:
    if not style_value:
        return {}
    return {
        match.group(1).strip().lower(): match.group(2).strip()
        for match in _STYLE_PROP_RE.finditer(style_value)
    }


def _select_img_wrapper_tag(open_tag_stack: List[str]) -> str:
    if open_tag_stack and open_tag_stack[-1] in {
        "a",
        "button",
        "label",
        "li",
        "p",
        "span",
        "strong",
        "em",
        "td",
        "th",
    }:
        return "span"
    if any(tag in {"td", "th", "li"} for tag in reversed(open_tag_stack)):
        return "span"
    return "div"


def _perturb_img_tag(
    rng: random.Random,
    tag: str,
    attrs: list[tuple[str, str, str | None]],
    *,
    output_mode: str,
    open_tag_stack: List[str],
) -> str:
    strict_mode = is_strict_output_mode(output_mode)
    ultra_strict = output_mode in {"super_strict", "libero"}
    style_value = next(
        (value for attr_name, _, value in attrs if attr_name.lower() == "style"), None
    )
    style_props = _parse_style_props(style_value)

    attr_names = {attr_name.lower() for attr_name, _, _ in attrs}
    has_author_box = bool({"width", "height"} & attr_names) or any(
        prop in style_props
        for prop in (
            "width",
            "height",
            "max-width",
            "min-width",
            "max-height",
            "min-height",
        )
    )
    has_layout_lock = any(
        prop in style_props
        for prop in (
            "position",
            "top",
            "left",
            "right",
            "bottom",
            "display",
            "float",
            "clear",
            "transform",
            "margin",
            "margin-left",
            "margin-right",
            "margin-top",
            "margin-bottom",
            "padding",
            "padding-left",
            "padding-right",
            "padding-top",
            "padding-bottom",
        )
    ) or any(name in attr_names for name in ("align", "hspace", "vspace"))

    additions: list[tuple[str, str]] = []
    wrapper_style: list[str] = []

    if ultra_strict:
        if not has_layout_lock:
            if "margin-left" not in style_props and maybe(rng, 0.55):
                additions.append(("margin-left", f"{rint(rng, 0, 1)}px"))
            elif "padding-right" not in style_props and maybe(rng, 0.4):
                additions.append(("padding-right", f"{rint(rng, 0, 1)}px"))
        return apply_inline_styles(tag, additions) if additions else tag

    if not has_layout_lock:
        if not strict_mode and "position" not in style_props and maybe(rng, 0.8):
            additions.append(("position", "relative"))
            if "top" not in style_props and maybe(rng, 0.7):
                additions.append(("top", f"{rint(rng, -1, 1)}px"))
            if "left" not in style_props and maybe(rng, 0.7):
                additions.append(("left", f"{rint(rng, -1, 1)}px"))
        if "margin-left" not in style_props and maybe(rng, 0.5):
            additions.append(("margin-left", f"{rint(rng, 0, 1)}px"))
        elif (
            "padding-right" not in style_props
            and not has_author_box
            and maybe(rng, 0.35)
        ):
            additions.append(("padding-right", f"{rint(rng, 0, 1)}px"))
    elif not ultra_strict and maybe(rng, 0.45):
        if not strict_mode and maybe(rng, 0.6):
            wrapper_style.append("position:relative")
            if maybe(rng, 0.7):
                wrapper_style.append(f"left:{rint(rng, -1, 1)}px")
            if maybe(rng, 0.5):
                wrapper_style.append(f"top:{rint(rng, -1, 1)}px")
        if not has_author_box:
            wrapper_style.append(f"margin-left:{rint(rng, 0, 1)}px")

    updated_tag = apply_inline_styles(tag, additions) if additions else tag
    if not wrapper_style:
        return updated_tag

    wrapper_tag = _select_img_wrapper_tag(open_tag_stack)
    if wrapper_tag == "span" and not any(
        style.startswith("display:") for style in wrapper_style
    ):
        wrapper_style.insert(0, "display:inline-block")
    style_attr = ";".join(wrapper_style).strip(";")
    return f'<{wrapper_tag} style="{style_attr};">{updated_tag}</{wrapper_tag}>'


def wrap_text_node_chunked(
    rng: random.Random,
    text: str,
    opt: Opt,
    *,
    in_table_list: bool = False,
) -> str:
    if not text or not text.strip():
        return text
    allow_inline_block = not in_table_list

    per_word_rate = opt.per_word_rate if opt.enable_per_word_rate else 0.0
    wrap_chunk_rate = opt.wrap_chunk_rate if opt.enable_wrap_chunk_rate else 0.0

    if maybe(rng, per_word_rate):
        chunks = re.split(r"(\s+)", text)
        out: List[str] = []
        for ch in chunks:
            if not ch or ch.isspace():
                out.append(ch)
                continue
            toks = tokenize_text_preserving_entities(ch)
            rendered = []
            for kind, val in toks:
                if kind == "ws":
                    rendered.append(val)
                elif kind == "entity":
                    rendered.append(val)
                else:
                    rendered.append(html.escape(val, quote=False))
            chunk_out = "".join(rendered)
            if maybe(rng, 0.28):
                out.append(
                    f'<span style="{letter_style(rng, allow_inline_block=allow_inline_block)}">'
                    f"{chunk_out}</span>"
                )
            else:
                out.append(chunk_out)
        return "".join(out)

    toks = tokenize_text_preserving_entities(text)
    out: List[str] = []
    i = 0

    while i < len(toks):
        kind, val = toks[i]

        if kind == "ws":
            out.append(val)
            i += 1
            continue

        if kind == "entity":
            if maybe(rng, wrap_chunk_rate * 0.30):
                out.append(
                    f'<span style="{letter_style(rng, allow_inline_block=allow_inline_block)}">'
                    f"{val}</span>"
                )
            else:
                out.append(val)
            i += 1
            continue

        # char
        c = val
        is_punct = bool(re.match(r"[\.\,\!\?\:\;\-\—\(\)\[\]\{\}\'\"]", c))
        start_p = wrap_chunk_rate * (0.35 if is_punct else 1.0)

        if maybe(rng, start_p):
            L = rint(rng, opt.chunk_len_min, opt.chunk_len_max)
            chunk = []
            j = i
            while j < len(toks) and len(chunk) < L:
                k, v = toks[j]
                if k in ("ws", "entity"):
                    break
                chunk.append(html.escape(v, quote=False))
                j += 1
            if chunk:
                out.append(
                    f'<span style="{letter_style(rng, allow_inline_block=allow_inline_block)}">'
                    f'{"".join(chunk)}</span>'
                )
                i = j
                continue

        out.append(html.escape(c, quote=False))
        i += 1

    return "".join(out)


def span_wrap_html(
    rng: random.Random,
    html_in: str,
    opt: Opt,
    synonym_patterns: List[Tuple[re.Pattern, List[str]]] | None = None,
    *,
    inline_styles: InlineStyleRules | None = None,
    wrap_spans: bool = True,
    output_mode: str | None = None,
) -> str:
    if synonym_patterns is None:
        synonym_patterns = []
    wrap_spans = wrap_spans and opt.enable_span_wrapping
    effective_output_mode = output_mode or opt.output_mode
    parts = TAG_SPLIT_RE.split(html_in)
    out: List[str] = []

    skip_depth = 0
    skip_tag_stack: List[str] = []
    table_list_depth = 0
    table_list_stack: List[str] = []
    table_list_tags = {
        "table",
        "thead",
        "tbody",
        "tr",
        "td",
        "th",
        "ul",
        "ol",
        "li",
    }
    tagname_re = re.compile(r"^</?\s*([a-zA-Z0-9:_-]+)")

    table_body_stack: list[int] = []
    open_tag_stack: List[str] = []

    for part in parts:
        if not part:
            continue

        if part.startswith("<") and part.endswith(">"):
            normalized_tag = normalize_table_cellspacing(part)
            styled_tag = normalized_tag
            m = tagname_re.match(normalized_tag)
            is_close = False
            is_self_close = False
            name = None
            if m:
                name = m.group(1).lower()
                is_close = normalized_tag.startswith("</")
                is_self_close = normalized_tag.rstrip().endswith("/>")
                if inline_styles and not is_close:
                    additions: list[tuple[str, str]] = []
                    if (
                        name in {"h1", "h2", "h3", "h4", "h5", "h6"}
                        and inline_styles.headings
                    ):
                        additions.extend(inline_styles.headings)
                    elif name == "blockquote" and inline_styles.blockquote:
                        additions.extend(inline_styles.blockquote)
                    elif name in {"code", "pre", "kbd", "samp"} and inline_styles.code:
                        additions.extend(inline_styles.code)
                    elif name == "a" and inline_styles.link:
                        additions.extend(inline_styles.link)
                    elif name in {"ul", "ol"} and inline_styles.list_style:
                        additions.extend(inline_styles.list_style)
                    elif name == "table" and inline_styles.table:
                        additions.extend(inline_styles.table)
                    elif name == "th" and inline_styles.th:
                        additions.extend(inline_styles.th)
                    elif name == "td" and inline_styles.cell:
                        additions.extend(inline_styles.cell)
                    elif name == "caption" and inline_styles.caption:
                        additions.extend(inline_styles.caption)
                    elif name == "button" and inline_styles.button:
                        additions.extend(inline_styles.button)
                    elif name == "input" and inline_styles.button:
                        if re.search(
                            r"type\\s*=\\s*(\"|\\\')?(button|submit|reset)\\1",
                            normalized_tag,
                            re.IGNORECASE,
                        ):
                            additions.extend(inline_styles.button)
                    elif name in {"small", "sub", "sup"} and inline_styles.small:
                        additions.extend(inline_styles.small)
                    elif name == "mark" and inline_styles.mark:
                        additions.extend(inline_styles.mark)
                    elif name == "abbr" and inline_styles.abbr:
                        additions.extend(inline_styles.abbr)
                    elif name in {"cite", "em"} and inline_styles.cite_em:
                        additions.extend(inline_styles.cite_em)
                    if name == "tr" and inline_styles.table_stripe and table_body_stack:
                        table_body_stack[-1] += 1
                        if table_body_stack[-1] % 2 == 0:
                            additions.extend(inline_styles.table_stripe)
                    if additions:
                        styled_tag = apply_inline_styles(normalized_tag, additions)

            if m and name == "img" and not is_close:
                attr_match = re.match(r"^<\s*[a-zA-Z0-9:_-]+([^>]*)>$", styled_tag)
                if attr_match:
                    rest = attr_match.group(1)
                    rest = rest.rstrip().rstrip("/")
                    attrs = _parse_tag_attrs(rest.strip())
                    if attrs or not rest.strip():
                        disable_image_mutation = effective_output_mode == "libero"
                        if (
                            not disable_image_mutation
                            and opt.enable_alt_text_randomization
                            and any(attr_name.lower() == "alt" for attr_name, _, _ in attrs)
                        ):
                            # Alt text is intentionally randomized to reduce fingerprinting surface.
                            randomized_alt = _random_alt_text(rng)
                            styled_tag = _update_attr_value(
                                styled_tag, "alt", randomized_alt
                            )
                            attrs = [
                                (
                                    attr_name,
                                    raw,
                                    (
                                        randomized_alt
                                        if attr_name.lower() == "alt"
                                        else value
                                    ),
                                )
                                for attr_name, raw, value in attrs
                            ]
                        if not disable_image_mutation:
                            has_width = any(
                                attr_name.lower() == "width" for attr_name, _, _ in attrs
                            )
                            has_height = any(
                                attr_name.lower() == "height" for attr_name, _, _ in attrs
                            )
                            if not has_width or not has_height:
                                style_value = next(
                                    (
                                        value
                                        for attr_name, _, value in attrs
                                        if attr_name.lower() == "style"
                                    ),
                                    None,
                                )
                                width_value = None
                                if not has_width:
                                    width_value = _extract_px_style_value(
                                        style_value, "width"
                                    )
                                    if width_value is None:
                                        width_value = str(rint(rng, 300, 350))
                                    styled_tag = _add_attr_if_missing(
                                        styled_tag, "width", width_value
                                    )
                                    attrs.append(
                                        ("width", f'width="{width_value}"', width_value)
                                    )
                            styled_tag = _perturb_img_tag(
                                rng,
                                styled_tag,
                                attrs,
                                output_mode=effective_output_mode,
                                open_tag_stack=open_tag_stack,
                            )

            if m and name == "tbody" and not is_self_close:
                if not is_close:
                    table_body_stack.append(0)
                elif table_body_stack:
                    table_body_stack.pop()

            reordered_tag = reorder_tag_attributes(rng, styled_tag)
            out.append(reordered_tag)
            if reordered_tag.count("<") != 1:
                continue

            m = tagname_re.match(reordered_tag)
            if m:
                name = m.group(1).lower()
                is_close = reordered_tag.startswith("</")
                is_self_close = reordered_tag.rstrip().endswith("/>")

                if not is_self_close:
                    if not is_close:
                        open_tag_stack.append(name)
                    elif open_tag_stack and open_tag_stack[-1] == name:
                        open_tag_stack.pop()
                    elif is_close and name in open_tag_stack:
                        open_tag_stack[:] = open_tag_stack[: open_tag_stack.index(name)]

                if name in SKIP_TEXT_INSIDE and not is_self_close:
                    if not is_close:
                        skip_depth += 1
                        skip_tag_stack.append(name)
                    else:
                        if skip_tag_stack and skip_tag_stack[-1] == name:
                            skip_tag_stack.pop()
                            skip_depth = max(0, skip_depth - 1)
                if name in table_list_tags and not is_self_close:
                    if not is_close:
                        table_list_depth += 1
                        table_list_stack.append(name)
                    else:
                        if table_list_stack and table_list_stack[-1] == name:
                            table_list_stack.pop()
                            table_list_depth = max(0, table_list_depth - 1)
            continue

        # text node
        in_table_list = table_list_depth > 0
        if skip_depth > 0:
            if skip_tag_stack and skip_tag_stack[-1] == "a":
                segments = TEMPLATE_SPLIT_RE.split(part)
                for segment in segments:
                    if not segment:
                        continue
                    if TEMPLATE_SPLIT_RE.fullmatch(segment):
                        out.append(segment)
                        continue
                    normalized = normalize_text_whitespace(segment)
                    with_synonyms = apply_synonyms(normalized, rng, synonym_patterns)
                    if wrap_spans:
                        out.append(
                            wrap_text_node_chunked(
                                rng,
                                with_synonyms,
                                opt,
                                in_table_list=in_table_list,
                            )
                        )
                    else:
                        out.append(with_synonyms)
            else:
                out.append(part)
        else:
            segments = TEMPLATE_SPLIT_RE.split(part)
            for segment in segments:
                if not segment:
                    continue
                if TEMPLATE_SPLIT_RE.fullmatch(segment):
                    out.append(segment)
                    continue
                normalized = normalize_text_whitespace(segment)
                if not normalized.strip():
                    out.append(normalized)
                    continue
                with_synonyms = apply_synonyms(normalized, rng, synonym_patterns)
                if wrap_spans:
                    out.append(
                        wrap_text_node_chunked(
                            rng,
                            with_synonyms,
                            opt,
                            in_table_list=in_table_list,
                        )
                    )
                else:
                    out.append(with_synonyms)

    return "".join(out)


def _random_alt_text(rng: random.Random) -> str:
    length = rint(rng, 6, 14)
    alphabet = string.ascii_lowercase + string.digits
    return "".join(rng.choice(alphabet) for _ in range(length))
