from fingerprintless_html_engine.html_utils import encode_quoted_printable_html, minify_output_html


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
