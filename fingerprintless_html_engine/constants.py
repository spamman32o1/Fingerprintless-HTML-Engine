from __future__ import annotations

import re

FONT_STACKS = [
    'system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif',
    'system-ui, -apple-system, "Segoe UI Variable", "Segoe UI", Roboto, Arial, sans-serif',
]

TEXT_COLORS = ["#111", "#121212", "#0f0f0f"]
BG_COLORS = ["#fff", "#fefefe", "#fcfcfc"]

ENTITY_RE = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]+|#[0-9]+|#x[0-9A-Fa-f]+);")
TAG_SPLIT_RE = re.compile(r"(<[^>]+>)")
HTML_LANG_RE = re.compile(r"<html[^>]*?\blang\s*=\s*['\"]?([a-zA-Z0-9-]+)", re.IGNORECASE)
BODY_RE = re.compile(r"<body[^>]*>(.*?)</body>", re.IGNORECASE | re.DOTALL)
TEMPLATE_SPLIT_RE = re.compile(r"(##.*?##)", re.DOTALL)
TABLE_TAG_RE = re.compile(r"<table([^>]*)>", re.IGNORECASE)
CELLSPACING_ATTR_RE = re.compile(r"\bcellspacing\s*=\s*([\"']?)([^\"'\s>]+)\1", re.IGNORECASE)
STYLE_ATTR_RE = re.compile(r"\bstyle\s*=\s*([\"'])(.*?)\1", re.IGNORECASE | re.DOTALL)
CENTER_TAG_RE = re.compile(r"^<\s*(/?)\s*center\b([^>]*)>$", re.IGNORECASE)

# Skip modifying text inside these tags (includes <a> per your request)
SKIP_TEXT_INSIDE = {"script", "style", "textarea", "code", "pre", "a"}
SAFE_WRAPPER_TAGS = {"div", "section", "span"}
VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}

JSONLD_MUTATION_POOL = [
    {},
    {"@context": ""},
    {"@context": None},
    [],
    [{}],
    {"x": 1},
    {"seed": "a9"},
]

FORBIDDEN_BRAND_RE = re.compile(
    r"\b(google|amazon|apple|microsoft|samsung|sony|nike|adidas|coca[- ]?cola|pepsi|tesla)\b",
    re.IGNORECASE,
)

FORBIDDEN_URL_RE = re.compile(r"https?://[^\s\"'>]+", re.IGNORECASE)

FALLBACK_ENCODINGS = ("latin-1", "windows-1252")

ATTR_RE = re.compile(r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)(\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s\"'>]+))?")
NUMERIC_VALUE_RE = re.compile(r"^\d+(?:\.\d+)?$")
