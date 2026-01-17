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


def build_synonym_patterns(groups: List[List[str]]) -> List[Tuple[re.Pattern, List[str]]]:
    patterns: List[Tuple[re.Pattern, List[str]]] = []
    for group in groups:
        escaped = sorted((re.escape(word) for word in group), key=len, reverse=True)
        if not escaped:
            continue
        pattern = re.compile(rf"(?i)(?<!\w)(?:{'|'.join(escaped)})(?!\w)")
        patterns.append((pattern, group))
    return patterns


def apply_synonyms(text: str, rng: random.Random, patterns: List[Tuple[re.Pattern, List[str]]]) -> str:
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

    if maybe(rng, opt.per_word_rate):
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
            if maybe(rng, opt.wrap_chunk_rate * 0.30):
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
        start_p = opt.wrap_chunk_rate * (0.35 if is_punct else 1.0)

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
) -> str:
    if synonym_patterns is None:
        synonym_patterns = []
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
                    if name in {"h1", "h2", "h3", "h4", "h5", "h6"} and inline_styles.headings:
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
                            r'type\\s*=\\s*(\"|\\\')?(button|submit|reset)\\1',
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
                        if any(attr_name.lower() == "alt" for attr_name, _, _ in attrs):
                            # Alt text is intentionally randomized to reduce fingerprinting surface.
                            styled_tag = _update_attr_value(styled_tag, "alt", _random_alt_text(rng))

            if m and name == "tbody" and not is_self_close:
                if not is_close:
                    table_body_stack.append(0)
                elif table_body_stack:
                    table_body_stack.pop()

            reordered_tag = reorder_tag_attributes(rng, styled_tag)
            out.append(reordered_tag)
            m = tagname_re.match(reordered_tag)
            if m:
                name = m.group(1).lower()
                is_close = reordered_tag.startswith("</")
                is_self_close = reordered_tag.rstrip().endswith("/>")

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
                    out.append(
                        wrap_text_node_chunked(
                            rng,
                            with_synonyms,
                            opt,
                            in_table_list=in_table_list,
                        )
                    )
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
                out.append(
                    wrap_text_node_chunked(
                        rng,
                        with_synonyms,
                        opt,
                        in_table_list=in_table_list,
                    )
                )

    return "".join(out)


def _random_alt_text(rng: random.Random) -> str:
    length = rint(rng, 6, 14)
    alphabet = string.ascii_lowercase + string.digits
    return "".join(rng.choice(alphabet) for _ in range(length))
