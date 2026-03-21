import random

from fingerprintless_html_engine.css_utils import SourceColorContext, random_css
from fingerprintless_html_engine.variant import analyze_source_colors


def test_analyze_source_colors_prefers_body_and_repeated_layout_colors():
    html = """
    <body text="#222222" bgcolor="#fafafa" style="color:#333333;background-color:#ffffff;">
      <table bgcolor="#fefefe"><tr><td style="background-color:#fefefe;color:#444444">A</td></tr></table>
      <table><tr><td style="background-color:#fefefe;color:#444444">B</td></tr></table>
    </body>
    """

    context = analyze_source_colors(html)

    assert context.source_text_color == "#333333"
    assert context.source_bg_color == "#ffffff"
    assert "#444444" in context.dominant_text_candidates
    assert "#fefefe" in context.dominant_bg_candidates


def test_random_css_preserves_readable_source_colors():
    body_css, _, _, _ = random_css(
        random.Random(5),
        source_color_context=SourceColorContext(
            source_text_color="#222222",
            source_bg_color="#f9f7f1",
        ),
    )

    assert "background-color: #f9f7f1;" in body_css
    assert "color: #222222;" in body_css


def test_random_css_falls_back_to_safe_text_when_source_pair_lacks_contrast():
    body_css, _, _, _ = random_css(
        random.Random(9),
        source_color_context=SourceColorContext(
            source_text_color="#f4f4f4",
            source_bg_color="#ffffff",
        ),
    )

    assert "background-color: #ffffff;" in body_css
    assert "color: #111827;" in body_css
