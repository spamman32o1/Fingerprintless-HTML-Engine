from __future__ import annotations

import html
import random
import re
from typing import List, Tuple

from .constants import ENTITY_RE, SKIP_TEXT_INSIDE, TAG_SPLIT_RE, TEMPLATE_SPLIT_RE
from .css_utils import letter_style
from .models import Opt
from .random_utils import maybe, pick, rint
from .tag_utils import normalize_table_cellspacing, reorder_tag_attributes


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


def wrap_text_node_chunked(rng: random.Random, text: str, opt: Opt) -> str:
    if not text or not text.strip():
        return text

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
                out.append(f'<span style="{letter_style(rng)}">{chunk_out}</span>')
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
                out.append(f'<span style="{letter_style(rng)}">{val}</span>')
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
                out.append(f'<span style="{letter_style(rng)}">{"".join(chunk)}</span>')
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
) -> str:
    if synonym_patterns is None:
        synonym_patterns = []
    parts = TAG_SPLIT_RE.split(html_in)
    out: List[str] = []

    skip_depth = 0
    skip_tag_stack: List[str] = []
    tagname_re = re.compile(r"^</?\s*([a-zA-Z0-9:_-]+)")

    for part in parts:
        if not part:
            continue

        if part.startswith("<") and part.endswith(">"):
            normalized_tag = normalize_table_cellspacing(part)
            reordered_tag = reorder_tag_attributes(rng, normalized_tag)
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
            continue

        # text node
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
                    out.append(wrap_text_node_chunked(rng, with_synonyms, opt))
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
                    continue
                with_synonyms = apply_synonyms(normalized, rng, synonym_patterns)
                out.append(wrap_text_node_chunked(rng, with_synonyms, opt))

    return "".join(out)
