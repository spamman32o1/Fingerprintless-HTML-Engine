from __future__ import annotations

import base64

from fingerprintless_html_engine.image_utils import (
    ImageInliner,
    RemoteImageCache,
    classify_image_reference,
    infer_image_mime_type,
    inline_image_references,
)


class _StubResponse:
    def __init__(self, payload: bytes, content_type: str):
        self._payload = payload
        self._content_type = content_type
        self.headers = self

    def read(self) -> bytes:
        return self._payload

    def get_content_type(self) -> str:
        return self._content_type

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_classify_image_reference_supports_remote_data_and_local_refs() -> None:
    assert classify_image_reference("https://example.com/a.png").kind == "remote"
    assert classify_image_reference("data:image/png;base64,abcd").kind == "data"
    assert classify_image_reference("images/a.png").kind == "local"


def test_inline_image_references_reuses_remote_cache(monkeypatch) -> None:
    payload = b"\x89PNG\r\n\x1a\nPNGDATA"
    calls: list[str] = []

    def _fake_urlopen(request):
        calls.append(request.full_url)
        return _StubResponse(payload, "application/octet-stream")

    monkeypatch.setattr("fingerprintless_html_engine.image_utils.urlopen", _fake_urlopen)

    cache = RemoteImageCache(enabled=True)
    html = (
        '<img src="https://example.com/a.png">'
        '<div style="background-image:url(https://example.com/a.png)"></div>'
    )
    rendered = inline_image_references(html, cache=cache)

    expected = "data:image/png;base64," + base64.b64encode(payload).decode("ascii")
    assert rendered.count(expected) == 2
    assert calls == ["https://example.com/a.png"]


def test_inline_image_references_preserves_data_urls_and_local_refs() -> None:
    html = (
        '<img src="data:image/gif;base64,R0lGODlhAQABAIAAAAUEBA==">'
        '<div style="background-image:url(/static/example.png)"></div>'
    )

    rendered = inline_image_references(html)

    assert rendered == html


def test_image_inliner_without_cache_fetches_each_remote_reference(monkeypatch) -> None:
    payload = b"GIF89a..."
    calls: list[str] = []

    def _fake_urlopen(request):
        calls.append(request.full_url)
        return _StubResponse(payload, "image/gif")

    monkeypatch.setattr("fingerprintless_html_engine.image_utils.urlopen", _fake_urlopen)

    inliner = ImageInliner(cache=RemoteImageCache(enabled=False))
    html = '<img src="https://example.com/a.gif"><img src="https://example.com/a.gif">'
    rendered = inliner.inline_html(html)

    assert rendered.count("data:image/gif;base64,") == 2
    assert calls == ["https://example.com/a.gif", "https://example.com/a.gif"]


def test_infer_image_mime_type_sniffs_svg_before_url_extension() -> None:
    payload = b"<?xml version='1.0'?><svg xmlns='http://www.w3.org/2000/svg'></svg>"

    mime_type = infer_image_mime_type(payload, source_url="https://example.com/image.bin", header_mime=None)

    assert mime_type == "image/svg+xml"
