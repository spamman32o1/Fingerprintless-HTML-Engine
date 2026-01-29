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
