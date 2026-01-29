from fingerprintless_html_engine.html_utils import encode_quoted_printable_html


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
