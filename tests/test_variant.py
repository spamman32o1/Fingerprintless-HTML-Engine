import random

import pytest

from fingerprintless_html_engine.css_utils import InlineStyleRules
from fingerprintless_html_engine.models import Opt
from fingerprintless_html_engine.variant import build_variant


@pytest.mark.parametrize("output_mode", ["super_strict", "libero"])
def test_build_variant_applies_inline_styles_in_strict_family_modes(monkeypatch, output_mode):
    inline_rules = InlineStyleRules(
        headings=(("--inline-heading", "1"),),
        blockquote=None,
        code=None,
        link=(("--inline-link", "1"),),
        list_style=(("--inline-list", "1"),),
        table=(("--inline-table", "1"),),
        cell=(("--inline-cell", "1"),),
        th=(("--inline-th", "1"),),
        table_stripe=None,
        caption=None,
        button=tuple(),
        small=tuple(),
        mark=tuple(),
        abbr=tuple(),
        cite_em=None,
    )

    monkeypatch.setattr(
        "fingerprintless_html_engine.variant.randomize_opt_for_variant",
        lambda rng, opt: opt,
    )
    monkeypatch.setattr(
        "fingerprintless_html_engine.variant.random_css",
        lambda *args, **kwargs: ("", "", "", inline_rules),
    )

    content_html = (
        '<table align="center" cellpadding="3" cellspacing="2">'
        "<tr><th>H</th><td>C <a href=\"#\">L</a></td></tr>"
        "</table>"
        "<ul><li>one</li></ul>"
        "<h2>Heading</h2>"
    )
    rendered = build_variant(
        rng=random.Random(7),
        content_html=content_html,
        opt=Opt(count=1, output_mode=output_mode, enable_span_wrapping=False),
        idx=0,
        lang="en",
        title="T",
    )

    assert "<style>" not in rendered
    assert "<table" in rendered and "--inline-table:1" in rendered
    assert "<th" in rendered and "--inline-th:1" in rendered
    assert "<td" in rendered and "--inline-cell:1" in rendered
    assert "<a " in rendered and "--inline-link:1" in rendered
    assert "<ul" in rendered and "--inline-list:1" in rendered
    assert "<h2" in rendered and "--inline-heading:1" in rendered

    # strict normalization should still be present alongside inline fallback styles
    assert "list-style-position:outside" in rendered
    assert "padding-left:20px" in rendered
    assert "border-collapse:collapse" in rendered


def test_build_variant_keeps_ie_comments_in_strict_mode(monkeypatch):
    monkeypatch.setattr(
        "fingerprintless_html_engine.variant.randomize_opt_for_variant",
        lambda rng, opt: opt,
    )

    rendered = build_variant(
        rng=random.Random(3),
        content_html="<p>Hello</p>",
        opt=Opt(
            count=1,
            output_mode="strict",
            enable_span_wrapping=False,
            ie_condition_randomize=True,
        ),
        idx=0,
        lang="en",
        title="T",
    )

    assert "<!--[if" in rendered
    assert "<![endif]-->" in rendered
