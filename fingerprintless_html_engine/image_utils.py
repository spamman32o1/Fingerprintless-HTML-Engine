from __future__ import annotations

import base64
import io
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



#: Largest ``src`` data URI that is decoded for image noise. Anything bigger is
#: left byte-identical so one huge inline image cannot stall a run.
_MAX_JITTER_PAYLOAD_BYTES = 12 * 1024 * 1024
#: Formats Pillow can decode *and* re-encode without losing transparency or
#: animation semantics. GIF has no palette space for a one-off colour, SVG has no
#: pixels, and AVIF has no encoder in the supported Pillow range, so all three are
#: left byte-identical.
_JITTERABLE_FORMATS = {"PNG", "JPEG", "WEBP", "BMP"}
#: WebP silently falls back to lossy encoding on re-save, which distorts the whole
#: image, so only lossless sources are re-encoded. Pillow does not expose the flag,
#: but the container does: a lossless bitstream is a ``VP8L`` chunk.
_WEBP_LOSSLESS_CHUNK = b"VP8L"
#: Native embedded profiles (latent pose, copyright, timestamps) are copied across
#: on re-encode, since metadata alone is not pixel content.
_PRESERVED_EMBEDDED_PROFILES = ("icc_profile", "exif", "xmp", "dpi")
_JITTER_ALPHA_THRESHOLD = 8
#: A lone one-step pixel is routinely erased by JPEG's DCT and 4:2:0 chroma
#: averaging, so JPEG gets a sparse speckle of larger steps spread over the image.
#: Distortion grows with margin, not with the number of points, so the rate is what
#: carries the entropy.
_JPEG_DITHER_MARGIN = 3
_JPEG_DITHER_RATE = 0.02
_JPEG_MAX_DITHER_POINTS = 6000
#: Highest mean channel difference a JPEG re-encode may introduce. Above this the
#: source is already heavily compressed and the payload is left byte-identical.
_JPEG_MAX_REENCODE_PSNR_LOSS = 2.0
_DATA_URI_RE = re.compile(
    r"^data:(?P<mime>image/[\w.+-]+);base64,(?P<payload>[A-Za-z0-9+/=\s]+)$",
    re.IGNORECASE,
)
_SRC_ATTR_RE = re.compile(
    r"(?P<prefix>\bsrc\s*=\s*)(?P<open>[\"'])(?P<value>.*?)(?P=open)",
    re.IGNORECASE | re.DOTALL,
)
_CSS_URL_DATA_RE = re.compile(
    r"url\(\s*(?P<open>[\"']?)(?P<value>data:[^)]*?)(?P=open)\s*\)",
    re.IGNORECASE | re.DOTALL,
)


def _pillow_image_module():
    """Return the ``PIL.Image`` module, or ``None`` when Pillow is absent."""
    try:
        from PIL import Image  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - depends on the environment
        return None
    return Image


def _image_chops():
    try:
        from PIL import ImageChops  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - depends on the environment
        return None
    return ImageChops


def _decoded_payload_length(payload: str) -> int:
    stripped = "".join(payload.split())
    padding = len(stripped) - len(stripped.rstrip("="))
    return len(stripped) * 3 // 4 - padding


def _visible_pixel(rng: random.Random, image) -> tuple[int, int] | None:
    """Pick a random pixel that is actually visible, or ``None`` if none is."""
    width, height = image.size
    x = rng.randrange(width)
    y = rng.randrange(height)
    if image.mode != "RGBA":
        return x, y
    alpha = image.getchannel("A")
    if alpha.getextrema()[0] >= _JITTER_ALPHA_THRESHOLD:
        return x, y
    opaque = [
        (px, py)
        for py in range(height)
        for px in range(width)
        if alpha.getpixel((px, py)) >= _JITTER_ALPHA_THRESHOLD
    ]
    if not opaque:
        return None
    return opaque[rng.randrange(len(opaque))]


def _color_values(rng: random.Random, value: int, delta: int) -> set[int]:
    """Candidate ``value + delta`` variants that stay inside a valid colour range."""
    candidates = {value + delta, value - delta}
    return {v for v in candidates if 0 <= v <= 255} or {max(0, min(255, value + delta))}


def _jitter_pixel(rng: random.Random, image) -> bool:
    """Nudge one colour channel of one visible pixel by ±1.

    A single-step change in one channel is invisible, yet re-encoding yields a
    different byte stream, so the base64 payload becomes a different string.
    Only colour channels are touched; a trailing alpha channel stays intact.

    Returns ``False`` when the image has no pixel that can be changed, for
    example a fully transparent PNG.
    """
    if image.size[0] < 1 or image.size[1] < 1:
        return False
    point = _visible_pixel(rng, image)
    if point is None:
        return False
    x, y = point

    channels = list(image.getpixel((x, y)))
    color_channels = 1 if image.mode in {"L", "LA"} else 3
    index = rng.randrange(color_channels)
    channels[index] = rng.choice(sorted(_color_values(rng, channels[index], 1)))
    image.putpixel((x, y), tuple(channels))
    return True


def _jitter_pixels_for_jpeg(rng: random.Random, image) -> bool:
    """Dither a sparse speckle of ±N pixels so JPEG re-encoding keeps the change.

    A lone one-step pixel is routinely erased by quantization and chroma
    averaging. A small number of marginal changes spread across the image
    survives re-encoding while staying visually indistinguishable, and its
    positions and directions still carry enough entropy to make every payload
    distinct.

    Returns ``False`` when the image has no pixel that can be changed.
    """
    width, height = image.size
    if width < 1 or height < 1:
        return False
    point = _visible_pixel(rng, image)
    if point is None:
        return False

    count = int(width * height * _JPEG_DITHER_RATE) + 1
    count = min(count, _JPEG_MAX_DITHER_POINTS)
    for _ in range(count):
        x = rng.randrange(width)
        y = rng.randrange(height)
        channels = list(image.getpixel((x, y)))
        color_channels = 1 if image.mode in {"L", "LA"} else 3
        index = rng.randrange(color_channels)
        channels[index] = rng.choice(
            sorted(_color_values(rng, channels[index], _JPEG_DITHER_MARGIN))
        )
        image.putpixel((x, y), tuple(channels))
    return True


def _webp_is_lossless(raw: bytes) -> bool:
    """Report whether a WebP payload holds a lossless (``VP8L``) bitstream."""
    return raw[12:36].find(_WEBP_LOSSLESS_CHUNK) != -1


def _preserved_profiles(probe) -> dict[str, object]:
    profiles: dict[str, object] = {}
    for name in _PRESERVED_EMBEDDED_PROFILES:
        value = probe.info.get(name)
        if value:
            profiles[name] = value
    return profiles


def _jpeg_reencode_cost(original: bytes, encoded: str) -> float:
    """Mean channel difference between a JPEG and its re-encoded copy.

    Re-encoding a JPEG that is already at low quality compounds its artifacts,
    so this cheap measurement decides whether to keep the source bytes.
    """
    ImageChops = _image_chops()
    if ImageChops is None:  # pragma: no cover - Pillow was already required upstream
        return 0.0
    from PIL import Image

    with Image.open(io.BytesIO(original)) as before_image:
        before = before_image.convert("RGB")
    with Image.open(io.BytesIO(base64.b64decode(encoded))) as after_image:
        after = after_image.convert("RGB")
    histogram = ImageChops.difference(before, after).convert("L").histogram()
    total = sum(value * count for value, count in enumerate(histogram))
    return total / float(before.size[0] * before.size[1])


def jitter_data_uri(rng: random.Random, data_uri: str) -> str:
    """Return ``data_uri`` with imperceptible pixel noise, or unchanged.

    Returns the input untouched when it is not an inlinable raster data URI,
    when Pillow is unavailable, when the format cannot be re-encoded safely,
    or when the payload exceeds ``_MAX_JITTER_PAYLOAD_BYTES``. Callers must not
    treat an identical return value as an error: whole-document uniqueness is
    still enforced downstream.
    """
    match = _DATA_URI_RE.match(data_uri.strip())
    if not match:
        return data_uri
    payload = match.group("payload")
    if _decoded_payload_length(payload) > _MAX_JITTER_PAYLOAD_BYTES:
        return data_uri

    Image = _pillow_image_module()
    if Image is None:
        return data_uri
    try:
        raw = base64.b64decode("".join(payload.split()), validate=True)
    except (ValueError, TypeError):
        return data_uri

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            fmt = (probe.format or "").upper()
            if fmt not in _JITTERABLE_FORMATS:
                return data_uri
            probe.load()
            # ``quantization`` mirrors the source tables, so re-saving keeps the
            # source's compression level instead of silently flattening it.
            source_quantization = getattr(probe, "quantization", None)
            profiles = _preserved_profiles(probe)
            image = probe.copy()
    except Exception:  # malformed image payloads stay untouched
        return data_uri

    if fmt == "WEBP" and not _webp_is_lossless(raw):
        return data_uri

    try:
        changed = (
            _jitter_pixels_for_jpeg(rng, image)
            if fmt == "JPEG"
            else _jitter_pixel(rng, image)
        )
        if not changed:
            return data_uri
        buffer = io.BytesIO()
        if fmt == "JPEG":
            # 4:2:0 chroma averaging would swallow most of the speckle, so the
            # jittered image is written as 4:4:4 at the source's own quality and
            # then measured for fidelity below.
            save_kwargs: dict[str, object] = {"subsampling": 0, **profiles}
            if source_quantization:
                save_kwargs["qtables"] = source_quantization
            else:
                save_kwargs["quality"] = 95
            image.save(buffer, format="JPEG", **save_kwargs)
        elif fmt == "WEBP":
            image.save(buffer, format="WEBP", lossless=True, **profiles)
        else:
            image.save(buffer, format=fmt, **profiles)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:  # encoding failures must never break generation
        return data_uri
    finally:
        image.close()

    if encoded == "".join(payload.split()):
        return data_uri
    if fmt == "JPEG" and _jpeg_reencode_cost(raw, encoded) > _JPEG_MAX_REENCODE_PSNR_LOSS:
        # Re-encoding would visibly soften the source; leave it byte-identical.
        return data_uri
    mime = match.group("mime").lower()
    return f"data:{mime};base64,{encoded}"


def jitter_image_references(
    html_text: str, rng: random.Random, *, enabled: bool = True
) -> str:
    """Apply ``jitter_data_uri`` to every ``<img src>`` and CSS ``url()``.

    Each occurrence is jittered independently, so two references to the same
    image inside one variant become two distinct payloads.
    """
    if not enabled:
        return html_text

    def _jitter_src(match: re.Match[str]) -> str:
        value = match.group("value")
        rewritten = jitter_data_uri(rng, value)
        if rewritten == value:
            return match.group(0)
        return f"{match.group('prefix')}{match.group('open')}{rewritten}{match.group('open')}"

    def _jitter_css(match: re.Match[str]) -> str:
        value = match.group("value")
        rewritten = jitter_data_uri(rng, value)
        if rewritten == value:
            return match.group(0)
        return f"url({match.group('open')}{rewritten}{match.group('open')})"

    html_text = _SRC_ATTR_RE.sub(_jitter_src, html_text)
    return _CSS_URL_DATA_RE.sub(_jitter_css, html_text)


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
