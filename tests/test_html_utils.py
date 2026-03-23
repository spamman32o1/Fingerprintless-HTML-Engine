import warnings

import pytest
from fingerprintless_html_engine import html_utils
from fingerprintless_html_engine.html_utils import (
    encode_quoted_printable_html,
    extract_body_content_with_inline_safe_styles,
    extract_lang,
    minify_output_html,
)


def test_encode_quoted_printable_html_wraps_and_preserves_crlf() -> None:
    html_text = "=" + ("a" * 200)
    encoded = encode_quoted_printable_html(html_text)

    assert "\n" not in encoded.replace("\r\n", "")

    headers, body = encoded.split("\r\n\r\n", 1)
    assert "Content-Transfer-Encoding: quoted-printable" in headers

    lines = [line for line in body.split("\r\n") if line]
    assert lines[0].startswith("=3D")
    assert all(len(line) <= 76 for line in lines)


def test_encode_quoted_printable_html_does_not_wrap_inside_attribute_values() -> None:
    long_url = "https://example.com/" + ("a" * 90)
    html_text = f'<img src="{long_url}" alt="preview">'

    encoded = encode_quoted_printable_html(html_text)
    _, body = encoded.split("\r\n\r\n", 1)

    url_index = body.index(long_url)
    assert "=\r\n" not in body[url_index : url_index + len(long_url)]


def test_encode_quoted_printable_html_can_skip_headers() -> None:
    html_text = "<p>Hello</p>"

    encoded = encode_quoted_printable_html(html_text, include_headers=False)

    assert "Content-Transfer-Encoding" not in encoded
    assert "Content-Type" not in encoded
    assert "\r\n\r\n" not in encoded


def test_minify_output_html_pretty_output_formats_blocks() -> None:
    html_text = (
        "<!doctype html><html><head><title>Hi</title></head><body>"
        "<div><p>Hello <strong>World</strong> <a href=\"#\">Link</a></p>"
        "<p>Next</p></div></body></html>"
    )

    formatted = minify_output_html(html_text, pretty_output=True)

    assert formatted == (
        "<!doctype html>\n"
        "<html>\n"
        "    <head>\n"
        "        <title>Hi</title>\n"
        "    </head>\n"
        "    <body>\n"
        "        <div>\n"
        "            <p>Hello <strong>World</strong> <a href=\"#\">Link</a></p>\n"
        "            <p>Next</p>\n"
        "        </div>\n"
        "    </body>\n"
        "</html>"
    )


def test_extract_lang_uses_detected_majority_language_when_html_lang_missing(monkeypatch) -> None:
    class _FakeLanguage:
        def __init__(self, code: str) -> None:
            self.iso_code_639_1 = type("Iso", (), {"name": code.upper()})()

    class _FakeDetection:
        def __init__(self, language, start_index: int, end_index: int) -> None:
            self.language = language
            self.start_index = start_index
            self.end_index = end_index

    class _FakeDetector:
        def detect_multiple_languages_of(self, text: str):
            en = _FakeLanguage("en")
            es = _FakeLanguage("es")
            return [
                _FakeDetection(en, 0, 10),
                _FakeDetection(es, 11, 31),
            ]

        def detect_language_of(self, text: str):
            return _FakeLanguage("en")

    monkeypatch.setattr(html_utils, "_get_language_detector", lambda: _FakeDetector())

    html_text = "<html><body>Hello world hola mundo adios amigo</body></html>"
    assert extract_lang(html_text) == "es"


def test_extract_lang_defaults_to_en_when_detector_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(html_utils, "_get_language_detector", lambda: None)

    html_text = "<html><body>Hola mundo</body></html>"
    assert extract_lang(html_text) == "en"




def test_extract_lang_uses_custom_fallback_when_detection_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(html_utils, "_get_language_detector", lambda: None)

    html_text = "<html><body>Hola mundo</body></html>"
    assert extract_lang(html_text, fallback_lang="it") == "it"

def test_extract_lang_warns_once_when_lingua_missing(monkeypatch) -> None:
    monkeypatch.setattr(html_utils, "LanguageDetectorBuilder", None)
    monkeypatch.setattr(html_utils, "_LANGUAGE_DETECTOR", None)
    monkeypatch.setattr(html_utils, "_LINGUA_WARNING_EMITTED", False)

    html_text = "<html><body>Hola mundo</body></html>"

    with pytest.warns(UserWarning, match="Optional dependency 'lingua' is not installed"):
        assert extract_lang(html_text) == "en"

    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        assert extract_lang(html_text) == "en"
    assert not record


def test_extract_body_content_with_inline_safe_styles_preserves_supported_selectors() -> None:
    html_text = (
        "<html><head><style>"
        "p{margin-top:4px;}"
        ".message{color:#123456;}"
        ".logo-wrap img{display:block;}"
        "div > img{border:0;}"
        "a:hover{text-decoration:none;}"
        "</style></head>"
        '<body><div class="message logo-wrap"><p style="font-weight:700">Hi</p><img src="x.png"></div></body></html>'
    )

    body_html = extract_body_content_with_inline_safe_styles(html_text, strict_mode=True)

    assert '<div class="message logo-wrap" style="color:#123456;">' in body_html
    assert '<p style="font-weight:700; margin-top:4px;">Hi</p>' in body_html
    assert '<img src="x.png" style="display:block;">' in body_html
    assert 'border:0' not in body_html
    assert 'text-decoration:none' not in body_html


def test_extract_body_content_with_inline_safe_styles_skips_unsafe_at_rules_and_values() -> None:
    html_text = (
        "<html><head><style>"
        "@media screen {.message{color:red;}}"
        ".message{background-image:url(javascript:alert(1));padding:8px;}"
        "</style></head>"
        '<body><div class="message">Hi</div></body></html>'
    )

    body_html = extract_body_content_with_inline_safe_styles(html_text, strict_mode=True)

    assert '<div class="message" style="padding:8px;">Hi</div>' in body_html
    assert 'javascript:' not in body_html
    assert '@media' not in body_html
