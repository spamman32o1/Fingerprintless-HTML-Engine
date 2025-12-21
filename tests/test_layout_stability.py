import random

from fingerprintless_html_engine.css_utils import random_css
from fingerprintless_html_engine.models import Opt
from fingerprintless_html_engine.text_utils import span_wrap_html


def test_random_css_stabilizes_layout_for_letters():
    rng = random.Random(42)
    _, wrapper_css, _ = random_css(rng, stabilize_letters=True)

    assert any(
        display in wrapper_css for display in ("display:block;", "display:flow-root;")
    )
    assert "display:flex" not in wrapper_css
    assert "display:grid" not in wrapper_css
    assert "rotate(0.0deg)" in wrapper_css
    assert "skewX(0.0deg)" in wrapper_css
    assert "scale(1.0)" in wrapper_css
    assert "translate(" not in wrapper_css


def test_letter_wrapped_snapshot_spacing():
    rng = random.Random(1234)
    opt = Opt(
        count=1,
        wrap_chunk_rate=1.0,
        chunk_len_min=1,
        chunk_len_max=1,
        per_word_rate=0.0,
        noise_divs_max=0,
        max_nesting=1,
        ie_condition_randomize=False,
        structure_randomize=False,
    )
    html_in = "<p>Hello world</p>"

    rendered = span_wrap_html(rng, html_in, opt)

    expected = (
        "<p><span style=\"font-size:0.9989em;letter-spacing:0.0184em;opacity:1.0;position:"
        "relative;top:0.046px;display:inline-block;white-space:nowrap;transform:rotate(0.0deg);\""
        ">H</span><span style=\"font-size:0.9983em;letter-spacing:0.0141em;opacity:1.0;position:"
        "relative;top:0.0px;display:inline-block;white-space:nowrap;transform:rotate(0.0deg);\""
        ">e</span><span style=\"font-size:1.0051em;letter-spacing:0.0157em;opacity:1.0;position:"
        "relative;top:0.0px;display:inline-block;white-space:nowrap;transform:rotate(0.0deg);\""
        ">l</span><span style=\"font-size:0.9987em;letter-spacing:0.0109em;opacity:1.0;position:"
        "relative;top:0.078px;display:inline-block;white-space:nowrap;transform:rotate(0.0deg);\""
        ">l</span><span style=\"font-size:1.0007em;letter-spacing:0.0104em;opacity:1.0;position:"
        "relative;top:0.0px;display:inline-block;white-space:nowrap;transform:rotate(0.0deg);\""
        ">o</span> <span style=\"font-size:0.9981em;letter-spacing:-0.004em;opacity:1.0;position:"
        "relative;top:0.0px;display:inline-block;white-space:nowrap;transform:rotate(0.0deg);\""
        ">w</span><span style=\"font-size:0.9988em;letter-spacing:-0.002em;opacity:0.98;position:"
        "relative;top:0.007px;display:inline-block;white-space:nowrap;transform:rotate(0.0deg);\""
        ">o</span><span style=\"font-size:1.0008em;letter-spacing:0.0146em;opacity:1.0;position:"
        "relative;top:0.0px;display:inline-block;white-space:nowrap;transform:rotate(0.0deg);\""
        ">r</span><span style=\"font-size:0.9984em;letter-spacing:0.0028em;opacity:1.0;position:"
        "relative;top:0.0px;display:inline-block;white-space:nowrap;transform:rotate(0.0deg);\""
        ">l</span><span style=\"font-size:1.0067em;letter-spacing:0.0087em;opacity:1.0;position:"
        "relative;top:0.0px;display:inline-block;white-space:nowrap;transform:rotate(0.0deg);\""
        ">d</span></p>"
    )

    assert rendered == expected
