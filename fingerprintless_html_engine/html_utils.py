from __future__ import annotations

import re
import warnings
from collections import Counter

try:
    from lingua import LanguageDetectorBuilder
except ImportError:  # pragma: no cover - optional dependency
    LanguageDetectorBuilder = None

from .constants import BODY_RE, HTML_LANG_RE, SKIP_TEXT_INSIDE, TAG_SPLIT_RE, TEMPLATE_SPLIT_RE, VOID_ELEMENTS
from .models import _HtmlNode
from .safe_css_utils import inline_safe_embedded_css
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
WORD_RE = re.compile(r"\b[^\W\d_]+\b", flags=re.UNICODE)
_LANGUAGE_DETECTOR = None
_LINGUA_WARNING_EMITTED = False


def _collapse_intertag_whitespace(html_text: str) -> str:
    def _replacement(match: re.Match[str]) -> str:
        left_tag, left_name, right_tag, right_name = match.group(1), match.group(2), match.group(3), match.group(4)
        if left_name.lower() in INLINE_TAGS and right_name.lower() in INLINE_TAGS:
            return f"{left_tag} {right_tag}"
        return f"{left_tag}{right_tag}"

    return INTERTAG_WHITESPACE_RE.sub(_replacement, html_text)


def extract_lang(html_in: str, fallback_lang: str = "en") -> str:
    m = HTML_LANG_RE.search(html_in)
    if m:
        return m.group(1)

    detected = _detect_html_content_lang(html_in)
    if detected:
        return detected
    return fallback_lang


def _get_language_detector():
    global _LINGUA_WARNING_EMITTED
    global _LANGUAGE_DETECTOR
    if _LANGUAGE_DETECTOR is not None:
        return _LANGUAGE_DETECTOR

    if LanguageDetectorBuilder is None:
        if not _LINGUA_WARNING_EMITTED:
            warnings.warn(
                "Optional dependency 'lingua' is not installed. "
                "Language auto-detection is disabled; install it with `pip install lingua-language-detector` "
                "to improve automatic HTML language detection.",
                UserWarning,
                stacklevel=2,
            )
            _LINGUA_WARNING_EMITTED = True
        return None

    _LANGUAGE_DETECTOR = LanguageDetectorBuilder.from_all_languages().build()
    return _LANGUAGE_DETECTOR


def _language_to_html_code(language: object) -> str | None:
    iso = getattr(language, "iso_code_639_1", None)
    if iso is not None:
        name = getattr(iso, "name", None)
        if isinstance(name, str) and name:
            return name.lower()
        iso_string = str(iso)
        if iso_string:
            return iso_string.lower()

    lang_name = getattr(language, "name", None)
    if isinstance(lang_name, str) and lang_name:
        return lang_name.lower()
    return None


def _extract_visible_text(html_in: str) -> str:
    without_scripts = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html_in)
    without_tags = re.sub(r"(?s)<[^>]+>", " ", without_scripts)
    return re.sub(r"\s+", " ", without_tags).strip()


def _detect_html_content_lang(html_in: str) -> str | None:
    detector = _get_language_detector()
    if detector is None:
        return None

    text = _extract_visible_text(html_in)
    if not text:
        return None

    try:
        detections = detector.detect_multiple_languages_of(text)
    except Exception:  # pragma: no cover - detector robustness fallback
        detections = None

    if detections:
        language_words: Counter[object] = Counter()
        for detection in detections:
            language = getattr(detection, "language", None)
            if language is None:
                continue
            start = getattr(detection, "start_index", 0)
            end = getattr(detection, "end_index", -1)
            segment = text[start : end + 1]
            word_count = len(WORD_RE.findall(segment))
            if word_count:
                language_words[language] += word_count

        if language_words:
            winner = max(language_words.items(), key=lambda item: item[1])[0]
            code = _language_to_html_code(winner)
            if code:
                return code

    try:
        single = detector.detect_language_of(text)
    except Exception:  # pragma: no cover - detector robustness fallback
        single = None
    return _language_to_html_code(single) if single is not None else None


def extract_body_content(html_in: str) -> str:
    m = BODY_RE.search(html_in)
    if m:
        return m.group(1)

    stripped = re.sub(r"(?is)<!doctype[^>]*>", "", html_in)
    stripped = re.sub(r"(?is)<head[^>]*>.*?</head>", "", stripped)
    stripped = re.sub(r"(?is)</?html[^>]*>", "", stripped)
    stripped = re.sub(r"(?is)</?body[^>]*>", "", stripped)
    return stripped.strip()


def extract_body_content_with_inline_safe_styles(html_in: str, *, strict_mode: bool = False) -> str:
    return inline_safe_embedded_css(html_in, strict_mode=strict_mode)


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


def _parse_html_nodes(html_in: str) -> _HtmlNode:
    parts = TAG_SPLIT_RE.split(html_in)
    root = _HtmlNode(tag="__root__", open_tag="", close_tag="", children=[], text="")
    stack = [root]

    for part in parts:
        if not part:
            continue

        if part.startswith("<") and part.endswith(">"):
            if part.startswith("</"):
                name = _tag_name(part)
                if name and len(stack) > 1 and stack[-1].tag == name:
                    stack[-1].close_tag = part
                    stack.pop()
                else:
                    stack[-1].children.append(_HtmlNode(None, "", None, [], part))
                continue

            if part.startswith("<!") or part.startswith("<?"):
                stack[-1].children.append(_HtmlNode(None, "", None, [], part))
                continue

            name = _tag_name(part)
            if not name:
                stack[-1].children.append(_HtmlNode(None, "", None, [], part))
                continue

            is_self_closing = part.rstrip().endswith("/>") or name in VOID_ELEMENTS
            node = _HtmlNode(tag=name, open_tag=part, close_tag=None, children=[], text="", self_closing=is_self_closing)
            stack[-1].children.append(node)
            if not is_self_closing:
                stack.append(node)
            continue

        stack[-1].children.append(_HtmlNode(None, "", None, [], part))

    return root


def _tag_name(tag_text: str) -> str | None:
    m = re.match(r"^</?\s*([a-zA-Z0-9:_-]+)", tag_text)
    if not m:
        return None
    return m.group(1).lower()


def _is_inline_tag(tag_name: str | None) -> bool:
    return bool(tag_name and (tag_name in INLINE_TAGS or tag_name in VOID_ELEMENTS))


def _render_inline(node: _HtmlNode) -> str:
    if node.tag is None:
        return node.text
    if node.self_closing or node.tag in VOID_ELEMENTS:
        return node.open_tag
    inner = "".join(_render_inline(child) for child in node.children)
    close = node.close_tag or f"</{node.tag}>"
    return f"{node.open_tag}{inner}{close}"


def _format_block(node: _HtmlNode, indent: str, level: int) -> list[str]:
    if node.tag is None:
        text = node.text.strip()
        return [f"{indent * level}{text}"] if text else []

    if node.self_closing or node.tag in VOID_ELEMENTS:
        return [f"{indent * level}{node.open_tag}"]

    is_inline_only = all(child.tag is None or _is_inline_tag(child.tag) for child in node.children)
    open_tag = node.open_tag
    close_tag = node.close_tag or f"</{node.tag}>"

    if is_inline_only:
        inner = "".join(_render_inline(child) for child in node.children)
        return [f"{indent * level}{open_tag}{inner}{close_tag}"]

    lines = [f"{indent * level}{open_tag}"]
    inline_buffer: list[str] = []
    for child in node.children:
        if child.tag is None or _is_inline_tag(child.tag):
            inline_buffer.append(_render_inline(child))
            continue
        if inline_buffer:
            inline_content = "".join(inline_buffer)
            if inline_content.strip():
                lines.append(f"{indent * (level + 1)}{inline_content}")
            inline_buffer = []
        lines.extend(_format_block(child, indent, level + 1))

    if inline_buffer:
        inline_content = "".join(inline_buffer)
        if inline_content.strip():
            lines.append(f"{indent * (level + 1)}{inline_content}")

    lines.append(f"{indent * level}{close_tag}")
    return lines


def _pretty_format_html(html_text: str, *, indent: str = "    ") -> str:
    root = _parse_html_nodes(html_text)
    lines: list[str] = []
    for child in root.children:
        if child.tag is None:
            text = child.text.strip()
            if text:
                lines.append(text)
            continue
        lines.extend(_format_block(child, indent, 0))
    return "\n".join(lines)


def minify_output_html(html_text: str, *, pretty_output: bool = False) -> str:
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
            elif pretty_output and collapsed:
                out.append(" ")

    minified = "".join(out)
    minified = _collapse_intertag_whitespace(minified)
    minified = minified.strip()
    if pretty_output:
        return _pretty_format_html(minified)
    return minified


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
    encoded: list[str] = []
    for char in token:
        codepoint = ord(char)
        if codepoint in (9, 32):
            encoded.append(char)
        elif 33 <= codepoint <= 126 and (char != "=" or not encode_equals):
            encoded.append(char)
        elif codepoint < 32 or codepoint == 127 or (char == "=" and encode_equals):
            encoded.append(f"={codepoint:02X}")
        else:
            encoded.append(char)
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
        equals = encode_equals if override_encode_equals is None else override_encode_equals
        segments: list[str] = []
        for char in token:
            codepoint = ord(char)
            if codepoint in (9, 32):
                segments.append(char)
            elif 33 <= codepoint <= 126 and (char != "=" or not equals):
                segments.append(char)
            elif codepoint < 32 or codepoint == 127 or (char == "=" and equals):
                segments.append(f"={codepoint:02X}")
            else:
                segments.append(char)
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
            encoded_tag = _encode_qp_token(tag_text, encoding=encoding, encode_equals=tag_equals)
            if soft_break_limit is None or len(encoded_tag) <= soft_break_limit:
                _add_segment(encoded_tag)
                return
            for token in _split_tag_attributes(tag_text):
                _add_segment(_encode_qp_token(token, encoding=encoding, encode_equals=tag_equals))
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
