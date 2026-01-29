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


def _encode_quoted_printable_bytes(
    body_bytes: bytes,
    *,
    maxlinelen: int = 76,
    encode_equals: bool = True,
) -> str:
    lines: list[str] = []
    line: list[str] = []
    line_len = 0
    soft_break_limit = maxlinelen - 1

    def _flush_line(add_soft_break: bool = False) -> None:
        nonlocal line, line_len
        if add_soft_break:
            lines.append("".join(line) + "=")
        else:
            lines.append("".join(line))
        line = []
        line_len = 0

    def _add_segment(segment: str) -> None:
        nonlocal line_len
        if line_len + len(segment) > soft_break_limit:
            _flush_line(add_soft_break=True)
        line.append(segment)
        line_len += len(segment)

    for idx, byte in enumerate(body_bytes):
        if byte == 13:
            continue
        if byte == 10:
            _flush_line(add_soft_break=False)
            continue
        next_is_newline = idx + 1 < len(body_bytes) and body_bytes[idx + 1] == 10
        at_end = idx + 1 == len(body_bytes)
        if byte in (9, 32) and (next_is_newline or at_end):
            segment = f"={byte:02X}"
        elif byte in (9, 32):
            segment = chr(byte)
        elif 33 <= byte <= 126 and (byte != 61 or not encode_equals):
            segment = chr(byte)
        else:
            segment = f"={byte:02X}"
        _add_segment(segment)

    _flush_line(add_soft_break=False)
    return "\r\n".join(lines)


def encode_quoted_printable_html(
    html_text: str,
    *,
    encoding: str = "utf-8",
    encode_equals: bool = True,
) -> str:
    """Encode HTML as quoted-printable text with CRLF line endings and headers."""
    normalized = html_text.replace("\r\n", "\n").replace("\r", "\n")
    body_bytes = normalized.encode(encoding)
    body = _encode_quoted_printable_bytes(body_bytes, maxlinelen=76, encode_equals=encode_equals)
    headers = (
        "Content-Type: text/html; charset=UTF-8\r\n"
        "Content-Transfer-Encoding: quoted-printable\r\n"
        "\r\n"
    )
    return f"{headers}{body}"
