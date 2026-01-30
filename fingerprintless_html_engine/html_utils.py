from __future__ import annotations

import re

from .constants import BODY_RE, HTML_LANG_RE, SKIP_TEXT_INSIDE, TAG_SPLIT_RE, TEMPLATE_SPLIT_RE
from .tag_utils import normalize_input_html

INLINE_TAGS = {
    "a",
    "abbr",
    "b",
    "bdi",
    "bdo",
    "br",
    "cite",
    "code",
    "data",
    "dfn",
    "em",
    "i",
    "img",
    "kbd",
    "mark",
    "q",
    "s",
    "samp",
    "small",
    "span",
    "strong",
    "sub",
    "sup",
    "time",
    "u",
    "var",
    "wbr",
}
INTERTAG_WHITESPACE_RE = re.compile(
    r"(</?\s*([a-zA-Z0-9:_-]+)[^>]*>)\s+(<\s*/?\s*([a-zA-Z0-9:_-]+)[^>]*>)"
)


def _collapse_intertag_whitespace(html_text: str) -> str:
    def _replacement(match: re.Match[str]) -> str:
        left_tag, left_name, right_tag, right_name = match.group(1), match.group(2), match.group(3), match.group(4)
        if left_name.lower() in INLINE_TAGS and right_name.lower() in INLINE_TAGS:
            return f"{left_tag} {right_tag}"
        return f"{left_tag}{right_tag}"

    return INTERTAG_WHITESPACE_RE.sub(_replacement, html_text)


def extract_lang(html_in: str) -> str:
    m = HTML_LANG_RE.search(html_in)
    if m:
        return m.group(1)
    return "en"


def extract_body_content(html_in: str) -> str:
    m = BODY_RE.search(html_in)
    if m:
        return m.group(1)

    stripped = re.sub(r"(?is)<!doctype[^>]*>", "", html_in)
    stripped = re.sub(r"(?is)<head[^>]*>.*?</head>", "", stripped)
    stripped = re.sub(r"(?is)</?html[^>]*>", "", stripped)
    stripped = re.sub(r"(?is)</?body[^>]*>", "", stripped)
    return stripped.strip()


def sanitize_input_html(html_in: str) -> str:
    """Remove HTML comments and collapse inter-tag whitespace.

    Comments are stripped using a DOTALL pattern to cover multiline blocks, and
    whitespace between tags (e.g., newlines/indentation) is collapsed from
    ">\\s+<" to "><" to avoid introducing visible gaps while leaving inline
    text unchanged.

    >>> sanitize_input_html("<span>foo</span> <span>bar</span>")
    '<span>foo</span> <span>bar</span>'
    """

    without_comments = re.sub(r"<!--.*?-->", "", html_in, flags=re.DOTALL)
    normalized = normalize_input_html(without_comments)
    return _collapse_intertag_whitespace(normalized)


def minify_output_html(html_text: str) -> str:
    parts = TAG_SPLIT_RE.split(html_text)
    out: list[str] = []
    tagname_re = re.compile(r"^</?\s*([a-zA-Z0-9:_-]+)")
    skip_stack: list[tuple[str, bool]] = []
    jsonld_type_re = re.compile(r"\btype\s*=\s*(['\"]?)application/ld\+json\1", re.IGNORECASE)

    for part in parts:
        if not part:
            continue

        if part.startswith("<") and part.endswith(">"):
            out.append(part)
            m = tagname_re.match(part)
            if m:
                name = m.group(1).lower()
                is_close = part.startswith("</")
                is_self_close = part.rstrip().endswith("/>")
                if name in SKIP_TEXT_INSIDE and not is_self_close:
                    if not is_close:
                        is_jsonld = name == "script" and bool(jsonld_type_re.search(part))
                        skip_stack.append((name, is_jsonld))
                    elif skip_stack and skip_stack[-1][0] == name:
                        skip_stack.pop()
            continue

        if skip_stack:
            name, is_jsonld = skip_stack[-1]
            if name in ("script", "style"):
                segments = TEMPLATE_SPLIT_RE.split(part)
                for segment in segments:
                    if not segment:
                        continue
                    if TEMPLATE_SPLIT_RE.fullmatch(segment):
                        out.append(segment)
                        continue
                    if name == "script" and is_jsonld:
                        collapsed = re.sub(r"\s+", " ", segment).strip()
                        if collapsed:
                            out.append(collapsed)
                    else:
                        collapsed = re.sub(r"\s+", " ", segment).strip()
                        if collapsed:
                            out.append(collapsed)
            else:
                out.append(part)
            continue

        segments = TEMPLATE_SPLIT_RE.split(part)
        for segment in segments:
            if not segment:
                continue
            if TEMPLATE_SPLIT_RE.fullmatch(segment):
                out.append(segment)
                continue
            collapsed = re.sub(r"\s+", " ", segment)
            if collapsed.strip():
                out.append(collapsed)

    minified = "".join(out)
    minified = _collapse_intertag_whitespace(minified)
    return minified.strip()


def _split_tag_attributes(tag: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    quote: str | None = None

    for char in tag:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue

        if char in ("'", '"'):
            quote = char
            current.append(char)
            continue

        if char.isspace():
            if current:
                tokens.append("".join(current))
                current = []
            current.append(char)
            continue

        current.append(char)

    if current:
        tokens.append("".join(current))
    return tokens


def _split_html_tokens(html_text: str) -> list[tuple[str, bool, int | None]]:
    parts = TAG_SPLIT_RE.split(html_text)
    tokens: list[tuple[str, bool, int | None]] = []
    tag_index = 0

    for part in parts:
        if not part:
            continue
        if part.startswith("<") and part.endswith(">"):
            tag_index += 1
            for token in _split_tag_attributes(part):
                tokens.append((token, True, tag_index))
        else:
            for char in part:
                tokens.append((char, False, None))

    return tokens


def _encode_qp_token(token: str, *, encoding: str, encode_equals: bool) -> str:
    token_bytes = token.encode(encoding)
    encoded: list[str] = []
    for byte in token_bytes:
        if byte in (9, 32):
            segment = chr(byte)
        elif 33 <= byte <= 126 and (byte != 61 or not encode_equals):
            segment = chr(byte)
        else:
            segment = f"={byte:02X}"
        encoded.append(segment)
    return "".join(encoded)


def _encode_quoted_printable_html(
    html_text: str,
    *,
    maxlinelen: int | None = 76,
    encoding: str,
    encode_equals: bool = True,
    preserve_tags: bool = True,
    wrap_inside_tags: bool = False,
    tag_encode_equals: bool | None = None,
) -> str:
    lines: list[str] = []
    line: list[str] = []
    line_len = 0
    soft_break_limit = None if maxlinelen is None else maxlinelen - 1

    def _encode_trailing_whitespace() -> None:
        nonlocal line_len
        if not line:
            return
        last = line[-1]
        match = re.search(r"[ \t]+$", last)
        if not match:
            return
        trailing = match.group(0)
        encoded = "".join(f"={ord(char):02X}" for char in trailing)
        line[-1] = last[: -len(trailing)] + encoded
        line_len += len(encoded) - len(trailing)

    def _flush_line(add_soft_break: bool = False) -> None:
        nonlocal line, line_len
        _encode_trailing_whitespace()
        if add_soft_break:
            lines.append("".join(line) + "=")
        else:
            lines.append("".join(line))
        line = []
        line_len = 0

    def _add_segment(segment: str) -> None:
        nonlocal line_len
        if soft_break_limit is not None and line_len + len(segment) > soft_break_limit and line:
            _flush_line(add_soft_break=True)
        line.append(segment)
        line_len += len(segment)

    def _iter_encoded_segments(token: str, *, override_encode_equals: bool | None = None) -> list[str]:
        token_bytes = token.encode(encoding)
        equals = encode_equals if override_encode_equals is None else override_encode_equals
        segments: list[str] = []
        for byte in token_bytes:
            if byte in (9, 32):
                segment = chr(byte)
            elif 33 <= byte <= 126 and (byte != 61 or not equals):
                segment = chr(byte)
            else:
                segment = f"={byte:02X}"
            segments.append(segment)
        return segments

    tag_buffer: list[str] = []
    current_tag: int | None = None

    def _flush_tag_buffer() -> None:
        nonlocal tag_buffer, current_tag
        if not tag_buffer:
            return
        tag_text = "".join(tag_buffer)
        tag_buffer = []
        current_tag = None
        if preserve_tags:
            _add_segment(tag_text)
            return
        tag_equals = tag_encode_equals if tag_encode_equals is not None else encode_equals
        if wrap_inside_tags:
            for segment in _iter_encoded_segments(tag_text, override_encode_equals=tag_equals):
                _add_segment(segment)
        else:
            encoded = "".join(_iter_encoded_segments(tag_text, override_encode_equals=tag_equals))
            _add_segment(encoded)

    for token, is_tag, tag_id in _split_html_tokens(html_text):
        if is_tag:
            if current_tag is None:
                current_tag = tag_id
            if tag_id != current_tag:
                _flush_tag_buffer()
                current_tag = tag_id
            tag_buffer.append(token)
            continue

        _flush_tag_buffer()
        if token == "\n":
            _flush_line(add_soft_break=False)
            continue
        for segment in _iter_encoded_segments(token):
            _add_segment(segment)

    _flush_tag_buffer()
    _flush_line(add_soft_break=False)
    return "\r\n".join(lines)


def encode_quoted_printable_html(
    html_text: str,
    *,
    encoding: str = "utf-8",
    encode_equals: bool = True,
    include_headers: bool = True,
    tag_mode: str = "safe",
    maxlinelen: int | None = 76,
) -> str:
    """Encode HTML as quoted-printable text with CRLF line endings."""
    if tag_mode not in {"safe", "encode"}:
        raise ValueError(f"Unknown tag_mode: {tag_mode}")
    preserve_tags = tag_mode == "safe"
    wrap_inside_tags = tag_mode != "safe"
    normalized = html_text.replace("\r\n", "\n").replace("\r", "\n")
    body = _encode_quoted_printable_html(
        normalized,
        maxlinelen=maxlinelen,
        encoding=encoding,
        encode_equals=encode_equals,
        preserve_tags=preserve_tags,
        wrap_inside_tags=wrap_inside_tags,
        tag_encode_equals=False if tag_mode == "safe" else None,
    )
    if not include_headers:
        return body
    headers = (
        "Content-Type: text/html; charset=UTF-8\r\n"
        "Content-Transfer-Encoding: quoted-printable\r\n"
        "\r\n"
    )
    return f"{headers}{body}"
