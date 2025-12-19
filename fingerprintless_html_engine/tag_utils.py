from __future__ import annotations

import re

from .constants import (
    ATTR_RE,
    CENTER_TAG_RE,
    CELLSPACING_ATTR_RE,
    NUMERIC_VALUE_RE,
    STYLE_ATTR_RE,
    TABLE_TAG_RE,
)


def _parse_attr_value(value_text: str | None) -> str | None:
    if not value_text:
        return None

    value = value_text.lstrip()
    if value.startswith("="):
        value = value[1:].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1]
    return value


def _css_spacing_value(raw_value: str | None) -> str:
    value = (raw_value or "0").strip()
    if NUMERIC_VALUE_RE.match(value):
        return f"{value}px"
    return value


def _css_border_value(raw_value: str | None) -> str:
    value = (raw_value or "").strip()
    if not value:
        return ""
    if NUMERIC_VALUE_RE.match(value):
        return f"{value}px solid"
    return value


def _style_has_prop(style_lower: str, prop: str) -> bool:
    return bool(re.search(rf"{re.escape(prop)}\s*:", style_lower))


def _merge_style_value(style_value: str | None, additions: list[tuple[str, str]]) -> str:
    merged_style = style_value or ""
    style_lower = merged_style.lower()
    to_add: list[str] = []
    for prop, value in additions:
        if not value or _style_has_prop(style_lower, prop):
            continue
        to_add.append(f"{prop}:{value};")

    if not to_add:
        return merged_style

    if merged_style and not merged_style.rstrip().endswith(";"):
        merged_style = f"{merged_style};"
    if merged_style:
        merged_style = f"{merged_style} {' '.join(to_add)}"
    else:
        merged_style = " ".join(to_add)
    return merged_style


def _parse_tag_attrs(attr_text: str) -> list[tuple[str, str, str | None]]:
    attrs: list[tuple[str, str, str | None]] = []
    pos = 0
    while pos < len(attr_text):
        while pos < len(attr_text) and attr_text[pos].isspace():
            pos += 1
        if pos >= len(attr_text):
            break

        m_attr = ATTR_RE.match(attr_text, pos)
        if not m_attr:
            return []

        raw = m_attr.group(0).strip()
        attr_name = m_attr.group(1)
        value = _parse_attr_value(m_attr.group(2))
        attrs.append((attr_name, raw, value))
        pos = m_attr.end()
    return attrs


def reorder_tag_attributes(rng, tag: str) -> str:
    """Shuffle attributes within a start/self-closing tag while preserving values."""

    if not tag.startswith("<") or tag.startswith("</") or tag.startswith("<!") or tag.startswith("<?"):
        return tag

    m = re.match(r"^<\s*([a-zA-Z0-9:_-]+)([^>]*)>$", tag)
    if not m:
        return tag

    name, rest = m.group(1), m.group(2)
    if not rest.strip():
        return tag

    trailing_slash = rest.rstrip().endswith("/")
    rest = rest.rstrip().rstrip("/")
    attr_text = rest.strip()

    attrs: list[str] = []
    pos = 0
    while pos < len(attr_text):
        while pos < len(attr_text) and attr_text[pos].isspace():
            pos += 1
        if pos >= len(attr_text):
            break

        m_attr = ATTR_RE.match(attr_text, pos)
        if not m_attr:
            return tag

        attrs.append(m_attr.group(0).strip())
        pos = m_attr.end()

    if len(attrs) < 2:
        return tag

    rng.shuffle(attrs)
    attr_str = " ".join(attrs)
    slash = " /" if trailing_slash else ""
    return f"<{name} {attr_str}{slash}>"


def _normalize_center_tag(tag: str) -> str:
    match = CENTER_TAG_RE.match(tag)
    if not match:
        return tag

    is_close = bool(match.group(1))
    rest = match.group(2)
    if is_close:
        return "</div>"

    trailing_slash = rest.rstrip().endswith("/")
    rest = rest.rstrip().rstrip("/")
    attrs = _parse_tag_attrs(rest.strip())
    if not attrs and rest.strip():
        return tag

    updated_attrs: list[str] = []
    style_value: str | None = None
    for attr_name, raw, value in attrs:
        if attr_name.lower() == "style":
            style_value = value or ""
        else:
            updated_attrs.append(raw)

    merged_style = _merge_style_value(style_value, [("text-align", "center")])
    if merged_style or style_value is not None:
        updated_attrs.append(f'style="{merged_style}"')

    attr_str = " ".join(updated_attrs).strip()
    slash = " /" if trailing_slash else ""
    if attr_str:
        return f"<div {attr_str}{slash}>"
    return f"<div{slash}>"


def _normalize_table_td_attrs(tag: str) -> str:
    if not tag.startswith("<") or tag.startswith("</") or tag.startswith("<!") or tag.startswith("<?"):
        return tag

    m = re.match(r"^<\s*([a-zA-Z0-9:_-]+)([^>]*)>$", tag)
    if not m:
        return tag

    name, rest = m.group(1), m.group(2)
    if name.lower() not in {"table", "td"} or not rest.strip():
        return tag

    trailing_slash = rest.rstrip().endswith("/")
    rest = rest.rstrip().rstrip("/")
    attrs = _parse_tag_attrs(rest.strip())
    if not attrs and rest.strip():
        return tag

    updated_attrs: list[str] = []
    style_value: str | None = None
    additions: list[tuple[str, str]] = []
    align_value: str | None = None

    for attr_name, raw, value in attrs:
        attr_lower = attr_name.lower()
        if attr_lower == "style":
            style_value = value or ""
            continue
        if attr_lower == "border":
            border_value = _css_border_value(value)
            if border_value:
                additions.append(("border", border_value))
            continue
        if attr_lower == "cellpadding":
            additions.append(("padding", _css_spacing_value(value)))
            continue
        if attr_lower == "width":
            additions.append(("width", _css_spacing_value(value)))
            continue
        if attr_lower == "height":
            additions.append(("height", _css_spacing_value(value)))
            continue
        if attr_lower == "bgcolor":
            additions.append(("background-color", value or ""))
            continue
        if attr_lower == "valign":
            valign_value = (value or "").strip().lower()
            if valign_value:
                additions.append(("vertical-align", valign_value))
            continue
        if attr_lower == "align":
            align_value = (value or "").strip().lower()
            continue
        updated_attrs.append(raw)

    if align_value:
        if name.lower() == "table":
            if align_value == "center":
                additions.append(("margin-left", "auto"))
                additions.append(("margin-right", "auto"))
            elif align_value == "left":
                additions.append(("margin-left", "0"))
                additions.append(("margin-right", "auto"))
            elif align_value == "right":
                additions.append(("margin-left", "auto"))
                additions.append(("margin-right", "0"))
        else:
            additions.append(("text-align", align_value))

    if not additions and style_value is None and len(updated_attrs) == len(attrs):
        return tag

    merged_style = _merge_style_value(style_value, additions)
    if merged_style or style_value is not None or additions:
        updated_attrs.append(f'style="{merged_style}"')

    attr_str = " ".join(updated_attrs).strip()
    slash = " /" if trailing_slash else ""
    if attr_str:
        return f"<{name} {attr_str}{slash}>"
    return f"<{name}{slash}>"


def normalize_table_cellspacing(tag: str) -> str:
    if not tag.startswith("<") or tag.startswith("</") or tag.startswith("<!") or tag.startswith("<?"):
        return tag

    m = re.match(r"^<\s*([a-zA-Z0-9:_-]+)([^>]*)>$", tag)
    if not m:
        return tag

    name, rest = m.group(1), m.group(2)
    if name.lower() != "table" or not rest.strip():
        return tag

    trailing_slash = rest.rstrip().endswith("/")
    rest = rest.rstrip().rstrip("/")
    attr_text = rest.strip()

    attrs: list[tuple[str, str, str | None]] = []
    pos = 0
    while pos < len(attr_text):
        while pos < len(attr_text) and attr_text[pos].isspace():
            pos += 1
        if pos >= len(attr_text):
            break

        m_attr = ATTR_RE.match(attr_text, pos)
        if not m_attr:
            return tag

        raw = m_attr.group(0).strip()
        attr_name = m_attr.group(1)
        value = _parse_attr_value(m_attr.group(2))
        attrs.append((attr_name, raw, value))
        pos = m_attr.end()

    cellspacing_value: str | None = None
    updated_attrs: list[str] = []
    style_value: str | None = None

    for attr_name, raw, value in attrs:
        if attr_name.lower() == "cellspacing":
            cellspacing_value = value
            continue
        if attr_name.lower() == "style":
            style_value = value or ""
            continue
        updated_attrs.append(raw)

    if cellspacing_value is None:
        return tag

    style_lower = (style_value or "").lower()
    additions: list[str] = []
    if "border-spacing" not in style_lower:
        additions.append(f"border-spacing: {_css_spacing_value(cellspacing_value)};")
    if "border-collapse" not in style_lower:
        additions.append("border-collapse: separate;")

    merged_style = style_value or ""
    if additions:
        if merged_style and not merged_style.rstrip().endswith(";"):
            merged_style = f"{merged_style};"
        if merged_style:
            merged_style = f"{merged_style} {' '.join(additions)}"
        else:
            merged_style = " ".join(additions)

    if merged_style or style_value is not None:
        updated_attrs.append(f'style="{merged_style}"')

    attr_str = " ".join(updated_attrs).strip()
    if attr_str:
        slash = " /" if trailing_slash else ""
        return f"<{name} {attr_str}{slash}>"
    slash = " /" if trailing_slash else ""
    return f"<{name}{slash}>"


def normalize_input_html(html_in: str) -> str:
    from .constants import TAG_SPLIT_RE

    parts = TAG_SPLIT_RE.split(html_in)
    out: list[str] = []

    for part in parts:
        if not part:
            continue
        if part.startswith("<") and part.endswith(">"):
            normalized = _normalize_center_tag(part)
            normalized = _normalize_table_td_attrs(normalized)
            out.append(normalized)
        else:
            out.append(part)

    return "".join(out)


def _replace_table_cellspacing(match: re.Match[str]) -> str:
    attrs = match.group(1)
    spacing_match = CELLSPACING_ATTR_RE.search(attrs)
    if not spacing_match:
        return match.group(0)

    spacing_value = spacing_match.group(2)
    attrs_clean = CELLSPACING_ATTR_RE.sub("", attrs)
    attrs_clean = re.sub(r"\s{2,}", " ", attrs_clean).strip()

    border_spacing = f"border-spacing:{_css_spacing_value(spacing_value)};"
    style_match = STYLE_ATTR_RE.search(attrs_clean)
    if style_match:
        quote = style_match.group(1)
        style_value = style_match.group(2).strip()
        if style_value and not style_value.rstrip().endswith(";"):
            style_value = f"{style_value};"
        style_value = f"{style_value}{border_spacing}"
        new_style = f'style={quote}{style_value}{quote}'
        attrs_clean = attrs_clean[: style_match.start()] + new_style + attrs_clean[style_match.end() :]
    else:
        attrs_clean = f'{attrs_clean} style="{border_spacing}"'.strip()

    return f"<table{(' ' + attrs_clean) if attrs_clean else ''}>"


def replace_cellspacing_with_css(html_text: str) -> str:
    return TABLE_TAG_RE.sub(_replace_table_cellspacing, html_text)
