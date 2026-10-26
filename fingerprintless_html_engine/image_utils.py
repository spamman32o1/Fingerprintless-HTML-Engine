from __future__ import annotations

import base64
import mimetypes
import random
import re
from dataclasses import dataclass, field
from typing import Callable, List
from urllib.error import URLError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

from .tag_utils import _parse_tag_attrs


_IMG_SRC_RE = re.compile(
    r'(?P<prefix><img\b[^>]*?\bsrc\s*=\s*)(?P<quote>["\']?)(?P<value>[^"\'\s>]+|.*?)(?P=quote)',
    re.IGNORECASE | re.DOTALL,
)
_CSS_URL_RE = re.compile(
    r'url\(\s*(?P<quote>["\']?)(?P<value>.*?)(?P=quote)\s*\)',
    re.IGNORECASE | re.DOTALL,
)
_REMOTE_SCHEMES = ("http://", "https://")


@dataclass
class RemoteImageCache:
    enabled: bool = True
    _data_urls: dict[str, str] = field(default_factory=dict)

    def get(self, url: str) -> str | None:
        if not self.enabled:
            return None
        return self._data_urls.get(url)

    def store(self, url: str, data_url: str) -> str:
        if self.enabled:
            self._data_urls[url] = data_url
        return data_url

    def get_or_create(self, url: str, builder: Callable[[str], str]) -> str:
        cached = self.get(url)
        if cached is not None:
            return cached
        data_url = builder(url)
        return self.store(url, data_url)


@dataclass(frozen=True)
class ImageReference:
    original: str
    kind: str


class ImageInliningError(RuntimeError):
    pass


class ImageInliner:
    def __init__(self, cache: RemoteImageCache | None = None):
        self.cache = cache or RemoteImageCache(enabled=True)

    def inline_html(self, html_text: str, *, enabled: bool = True) -> str:
        if not enabled:
            return html_text
        html_text = _IMG_SRC_RE.sub(self._replace_img_src, html_text)
        return _CSS_URL_RE.sub(self._replace_css_url, html_text)

    def _replace_img_src(self, match: re.Match[str]) -> str:
        value = match.group("value")
        rewritten = self._rewrite_reference(value)
        if rewritten == value:
            return match.group(0)
        quote = match.group("quote") or '"'
        return f"{match.group('prefix')}{quote}{rewritten}{quote}"

    def _replace_css_url(self, match: re.Match[str]) -> str:
        value = match.group("value").strip()
        rewritten = self._rewrite_reference(value)
        if rewritten == value:
            return match.group(0)
        quote = match.group("quote") or '"'
        return f"url({quote}{rewritten}{quote})"

    def _rewrite_reference(self, value: str) -> str:
        reference = classify_image_reference(value)
        if reference.kind != "remote":
            return value
        return self.cache.get_or_create(reference.original, self._download_as_data_url)

    def _download_as_data_url(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": "FingerprintlessHTML/1.0"})
        try:
            with urlopen(request) as response:  # nosec B310 - feature requires controlled remote fetches
                payload = response.read()
                header_mime = response.headers.get_content_type()
        except URLError as exc:  # pragma: no cover - network failures depend on environment
            raise ImageInliningError(f"Failed to download remote image '{url}': {exc}") from exc
        mime_type = infer_image_mime_type(payload, source_url=url, header_mime=header_mime)
        encoded = base64.b64encode(payload).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"


def classify_image_reference(value: str) -> ImageReference:
    stripped = value.strip()
    lowered = stripped.lower()
    if lowered.startswith("data:"):
        return ImageReference(original=stripped, kind="data")
    if lowered.startswith(_REMOTE_SCHEMES):
        return ImageReference(original=stripped, kind="remote")
    return ImageReference(original=stripped, kind="local")


def infer_image_mime_type(payload: bytes, *, source_url: str, header_mime: str | None = None) -> str:
    normalized_header = (header_mime or "").split(";", 1)[0].strip().lower()
    if normalized_header and normalized_header not in {"application/octet-stream", "binary/octet-stream"}:
        return normalized_header

    sniffed = _sniff_mime_from_bytes(payload)
    if sniffed:
        return sniffed

    guessed, _ = mimetypes.guess_type(unquote(urlsplit(source_url).path))
    if guessed:
        return guessed
    return "application/octet-stream"


def _sniff_mime_from_bytes(payload: bytes) -> str | None:
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if payload.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return "image/webp"
    if payload.startswith(b"BM"):
        return "image/bmp"
    if payload.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    leading = payload.lstrip()[:256].lower()
    if leading.startswith(b"<svg") or leading.startswith(b"<?xml") and b"<svg" in payload[:1024].lower():
        return "image/svg+xml"
    return None


def inline_image_references(
    html_text: str,
    *,
    enabled: bool = True,
    cache: RemoteImageCache | None = None,
) -> str:
    return ImageInliner(cache=cache).inline_html(html_text, enabled=enabled)


_TAG_ATTR_RE = re.compile(r"^<\s*([a-zA-Z0-9:_-]+)([^>]*)>$")


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

    m = _TAG_ATTR_RE.match(tag)
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


def apply_image_noise(
    rng: random.Random,
    tag: str,
    *,
    output_mode: str,
    open_tag_stack: List[str],
) -> str:
    """Apply fingerprint noise to a single ``<img>`` tag.

    Returns the tag untouched when it cannot be parsed or when ``libero`` mode
    forbids image mutation.
    """
    attr_match = _TAG_ATTR_RE.match(tag)
    if not attr_match:
        return tag

    rest = attr_match.group(2).rstrip().rstrip("/")
    attrs = _parse_tag_attrs(rest.strip())
    if not attrs and rest.strip():
        return tag

    if output_mode == "libero":
        return tag

    has_width = any(name.lower() == "width" for name, _, _ in attrs)
    if not has_width:
        style_value = next(
            (value for name, _, value in attrs if name.lower() == "style"), None
        )
        width_value = _extract_px_style_value(style_value, "width")
        if width_value is not None:
            tag = _add_attr_if_missing(tag, "width", width_value)

    return tag
