from __future__ import annotations

from dataclasses import dataclass
import re

from .constants import BODY_RE, VOID_ELEMENTS
from .css_utils import parse_inline_style_declarations
from .tag_utils import _parse_tag_attrs, apply_inline_styles

STYLE_BLOCK_RE = re.compile(r"(?is)<style[^>]*>(.*?)</style>")
RULE_RE = re.compile(r"(?is)([^{}]+)\{([^{}]+)\}")
TAG_TOKEN_RE = re.compile(r"(?is)<(/?)([a-zA-Z0-9:_-]+)([^>]*)>")
_SIMPLE_SELECTOR_TOKEN_RE = re.compile(r"(?:^[a-zA-Z][a-zA-Z0-9_-]*)|(?:[.#][a-zA-Z_][a-zA-Z0-9_-]*)")
_UNSAFE_STYLE_VALUE_RE = re.compile(r"(?i)(expression\s*\(|javascript\s*:|vbscript\s*:|-moz-binding|behavior\s*:|@import)")
_ALLOWED_STRICT_STYLE_PROPS = {
    "background",
    "background-color",
    "border",
    "border-bottom",
    "border-bottom-color",
    "border-bottom-style",
    "border-bottom-width",
    "border-collapse",
    "border-color",
    "border-left",
    "border-left-color",
    "border-left-style",
    "border-left-width",
    "border-radius",
    "border-right",
    "border-right-color",
    "border-right-style",
    "border-right-width",
    "border-spacing",
    "border-style",
    "border-top",
    "border-top-color",
    "border-top-style",
    "border-top-width",
    "border-width",
    "color",
    "display",
    "font",
    "font-family",
    "font-size",
    "font-style",
    "font-variant",
    "font-weight",
    "height",
    "letter-spacing",
    "line-height",
    "list-style",
    "list-style-position",
    "list-style-type",
    "margin",
    "margin-bottom",
    "margin-left",
    "margin-right",
    "margin-top",
    "max-width",
    "min-height",
    "min-width",
    "padding",
    "padding-bottom",
    "padding-left",
    "padding-right",
    "padding-top",
    "text-align",
    "text-decoration",
    "text-indent",
    "text-transform",
    "white-space",
    "width",
}


@dataclass(frozen=True)
class _SimpleSelector:
    tag_name: str | None
    id_name: str | None
    class_names: tuple[str, ...]


@dataclass(frozen=True)
class _TagContext:
    tag_name: str
    attrs: tuple[tuple[str, str, str | None], ...]


def _extract_embedded_style_blocks(document_html: str) -> list[str]:
    return [match.group(1) for match in STYLE_BLOCK_RE.finditer(document_html)]


def _extract_body_html(document_html: str) -> str:
    match = BODY_RE.search(document_html)
    if match:
        return match.group(1)

    stripped = re.sub(r"(?is)<!doctype[^>]*>", "", document_html)
    stripped = re.sub(r"(?is)<head[^>]*>.*?</head>", "", stripped)
    stripped = re.sub(r"(?is)</?html[^>]*>", "", stripped)
    stripped = re.sub(r"(?is)</?body[^>]*>", "", stripped)
    return stripped.strip()


def _parse_simple_selector(selector_part: str) -> _SimpleSelector | None:
    if not selector_part or any(token in selector_part for token in (">", "+", "~", "[", ":", "*")):
        return None

    parts = _SIMPLE_SELECTOR_TOKEN_RE.findall(selector_part)
    if not parts or "".join(parts) != selector_part:
        return None

    tag_name: str | None = None
    id_name: str | None = None
    class_names: list[str] = []
    for part in parts:
        if part.startswith("."):
            class_names.append(part[1:].lower())
        elif part.startswith("#"):
            if id_name is not None:
                return None
            id_name = part[1:]
        else:
            if tag_name is not None:
                return None
            tag_name = part.lower()
    return _SimpleSelector(tag_name=tag_name, id_name=id_name, class_names=tuple(class_names))


def _parse_selector(selector: str) -> tuple[_SimpleSelector, ...] | None:
    selector = " ".join(selector.strip().split())
    if not selector:
        return None

    parts = selector.split(" ")
    parsed: list[_SimpleSelector] = []
    for part in parts:
        parsed_part = _parse_simple_selector(part)
        if parsed_part is None:
            return None
        parsed.append(parsed_part)
    return tuple(parsed)


def _strip_at_rules(css_text: str) -> str:
    result: list[str] = []
    index = 0
    length = len(css_text)
    while index < length:
        if css_text[index] != "@":
            result.append(css_text[index])
            index += 1
            continue

        index += 1
        while index < length and css_text[index] not in "{;":
            index += 1
        if index >= length:
            break
        if css_text[index] == ";":
            index += 1
            continue

        depth = 1
        index += 1
        while index < length and depth > 0:
            if css_text[index] == "{":
                depth += 1
            elif css_text[index] == "}":
                depth -= 1
            index += 1
    return "".join(result)


def _sanitize_declarations(declarations: str, *, strict_mode: bool) -> list[tuple[str, str]]:
    parsed = parse_inline_style_declarations(declarations)
    sanitized: list[tuple[str, str]] = []
    for prop_name, prop_value in parsed.items():
        name = prop_name.strip().lower()
        value = prop_value.strip()
        if not name or not value:
            continue
        if _UNSAFE_STYLE_VALUE_RE.search(value):
            continue
        if strict_mode and name not in _ALLOWED_STRICT_STYLE_PROPS:
            continue
        sanitized.append((name, value))
    return sanitized


def _extract_safe_css_rules(document_html: str, *, strict_mode: bool) -> list[tuple[tuple[_SimpleSelector, ...], list[tuple[str, str]]]]:
    rules: list[tuple[tuple[_SimpleSelector, ...], list[tuple[str, str]]]] = []
    for style_block in _extract_embedded_style_blocks(document_html):
        css_text = re.sub(r"/\*.*?\*/", "", style_block, flags=re.DOTALL)
        css_text = _strip_at_rules(css_text)
        for selector_text, declarations in RULE_RE.findall(css_text):
            if "@" in selector_text:
                continue
            sanitized = _sanitize_declarations(declarations, strict_mode=strict_mode)
            if not sanitized:
                continue
            for selector in selector_text.split(","):
                parsed_selector = _parse_selector(selector)
                if parsed_selector is None:
                    continue
                rules.append((parsed_selector, sanitized))
    return rules


def _tag_matches_simple_selector(tag: _TagContext, selector: _SimpleSelector) -> bool:
    if selector.tag_name and selector.tag_name != tag.tag_name:
        return False
    attr_map = {name.lower(): value or "" for name, _raw, value in tag.attrs}
    if selector.id_name and attr_map.get("id") != selector.id_name:
        return False
    if selector.class_names:
        classes = {token.lower() for token in attr_map.get("class", "").split() if token}
        if any(class_name not in classes for class_name in selector.class_names):
            return False
    return True


def _selector_matches(tag: _TagContext, ancestors: list[_TagContext], selector: tuple[_SimpleSelector, ...]) -> bool:
    if not _tag_matches_simple_selector(tag, selector[-1]):
        return False
    ancestor_index = len(ancestors) - 1
    for selector_part in reversed(selector[:-1]):
        while ancestor_index >= 0 and not _tag_matches_simple_selector(ancestors[ancestor_index], selector_part):
            ancestor_index -= 1
        if ancestor_index < 0:
            return False
        ancestor_index -= 1
    return True


def inline_safe_embedded_css(document_html: str, *, strict_mode: bool) -> str:
    body_html = _extract_body_html(document_html)
    style_rules = _extract_safe_css_rules(document_html, strict_mode=strict_mode)
    if not style_rules:
        return body_html

    result: list[str] = []
    last_end = 0
    open_tags: list[_TagContext] = []
    for match in TAG_TOKEN_RE.finditer(body_html):
        result.append(body_html[last_end:match.start()])
        last_end = match.end()
        slash, raw_tag_name, attr_text = match.groups()
        tag_name = raw_tag_name.lower()
        tag_text = match.group(0)

        if tag_text.startswith("<!") or tag_text.startswith("<?"):
            result.append(tag_text)
            continue

        if slash:
            result.append(tag_text)
            for index in range(len(open_tags) - 1, -1, -1):
                if open_tags[index].tag_name == tag_name:
                    del open_tags[index:]
                    break
            continue

        attrs = tuple(_parse_tag_attrs(attr_text.strip().rstrip('/')))
        current_tag = _TagContext(tag_name=tag_name, attrs=attrs)
        additions: list[tuple[str, str]] = []
        for selector, declarations in style_rules:
            if _selector_matches(current_tag, open_tags, selector):
                additions.extend(declarations)
        result.append(apply_inline_styles(tag_text, additions) if additions else tag_text)

        is_self_closing = tag_text.rstrip().endswith("/>") or tag_name in VOID_ELEMENTS
        if not is_self_closing:
            open_tags.append(current_tag)

    result.append(body_html[last_end:])
    return "".join(result)
