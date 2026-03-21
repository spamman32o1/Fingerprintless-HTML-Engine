import random
import re

import pytest

from fingerprintless_html_engine.css_utils import (
    InlineStyleRules,
    SourceColorContext,
    contrast_ratio,
    parse_color_value,
)
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


def test_build_variant_randomizes_only_img_width_for_all_output_modes(monkeypatch):
    monkeypatch.setattr(
        "fingerprintless_html_engine.variant.randomize_opt_for_variant",
        lambda rng, opt: opt,
    )

    for output_mode in ("default", "strict", "super_strict", "libero"):
        rendered = build_variant(
            rng=random.Random(11),
            content_html='<img src="https://example.com/image.png">',
            opt=Opt(count=1, output_mode=output_mode, enable_span_wrapping=False),
            idx=0,
            lang="en",
            title="T",
        )

        img_match = re.search(r"<img\b[^>]*>", rendered, re.IGNORECASE)
        assert img_match is not None
        img_tag = img_match.group(0)

        width_match = re.search(r"\bwidth\s*=\s*[\"']?(\d+)", img_tag, re.IGNORECASE)
        height_match = re.search(r"\bheight\s*=", img_tag, re.IGNORECASE)

        assert width_match is not None
        assert height_match is None
        assert 300 <= int(width_match.group(1)) <= 350


def test_build_variant_does_not_autofill_img_height_for_qr_alt(monkeypatch):
    monkeypatch.setattr(
        "fingerprintless_html_engine.variant.randomize_opt_for_variant",
        lambda rng, opt: opt,
    )

    rendered = build_variant(
        rng=random.Random(11),
        content_html='<img src="https://example.com/qr.png" alt="Scan QR code">',
        opt=Opt(count=1, output_mode="default", enable_span_wrapping=False, enable_alt_text_randomization=False),
        idx=0,
        lang="en",
        title="T",
    )

    img_match = re.search(r"<img\b[^>]*>", rendered, re.IGNORECASE)
    assert img_match is not None
    img_tag = img_match.group(0)
    assert re.search(r"\bwidth\s*=", img_tag, re.IGNORECASE)
    assert not re.search(r"\bheight\s*=", img_tag, re.IGNORECASE)


def _extract_style_block(rendered: str) -> str:
    style_match = re.search(r"<style>(.*?)</style>", rendered, re.IGNORECASE | re.DOTALL)
    assert style_match is not None
    return style_match.group(1)


def _extract_rule(css_text: str, selector: str) -> str:
    rule_match = re.search(rf"{re.escape(selector)}\{{([^}}]*)\}}", css_text, re.IGNORECASE)
    assert rule_match is not None
    return rule_match.group(1)


def _extract_decl(rule_text: str, prop: str) -> str:
    decl_match = re.search(
        rf"(?:^|;)\s*{re.escape(prop)}\s*:\s*([^;}}]+)",
        rule_text,
        re.IGNORECASE,
    )
    assert decl_match is not None
    return decl_match.group(1).strip()


def _resolve_color(value: str, variables: dict[str, str]) -> str | None:
    value = value.strip()
    if value.startswith("var(") and value.endswith(")"):
        return parse_color_value(variables.get(value[4:-1].strip()))
    return parse_color_value(value)


def test_build_variant_keeps_body_links_and_buttons_contrast_safe_on_light_source_bg(monkeypatch):
    monkeypatch.setattr(
        "fingerprintless_html_engine.variant.randomize_opt_for_variant",
        lambda rng, opt: opt,
    )
    monkeypatch.setattr(
        "fingerprintless_html_engine.variant.analyze_source_colors",
        lambda _html: SourceColorContext(
            source_text_color="#ffffff",
            source_bg_color="#ffffff",
            dominant_text_candidates=("#ffffff", "#f9fafb", "#f3f4f6"),
            dominant_bg_candidates=("#ffffff", "#fefefe"),
        ),
    )
    monkeypatch.setattr(
        "fingerprintless_html_engine.css_utils.TEXT_COLORS",
        ["#ffffff", "#f9fafb", "#f3f4f6"],
    )
    monkeypatch.setattr(
        "fingerprintless_html_engine.css_utils.BG_COLORS",
        ["#ffffff", "#fefefe"],
    )
    monkeypatch.setattr("fingerprintless_html_engine.css_utils.pick", lambda rng, seq: list(seq)[0])
    monkeypatch.setattr("fingerprintless_html_engine.css_utils.maybe", lambda rng, probability: True)

    rendered = build_variant(
        rng=random.Random(13),
        content_html='<p>Hello <a href="https://example.com">link</a> <button>Go</button></p>',
        opt=Opt(count=1, output_mode="default", enable_span_wrapping=False),
        idx=0,
        lang="en",
        title="T",
    )

    css_text = _extract_style_block(rendered)
    body_rule = _extract_rule(css_text, "body")
    link_rule = _extract_rule(css_text, "a")
    button_rule = _extract_rule(css_text, "button,input[type=button],input[type=submit],input[type=reset]")

    variables = {
        "--bg": _extract_decl(body_rule, "--bg"),
        "--accent": _extract_decl(body_rule, "--accent"),
    }
    body_bg = _resolve_color(_extract_decl(body_rule, "background-color"), variables)
    body_fg = _resolve_color(_extract_decl(body_rule, "color"), variables)
    link_fg = _resolve_color(_extract_decl(link_rule, "color"), variables)
    button_bg = _resolve_color(_extract_decl(button_rule, "background"), variables)
    button_fg = _resolve_color(_extract_decl(button_rule, "color"), variables)

    assert body_bg is not None and body_fg is not None
    assert link_fg is not None and button_bg is not None and button_fg is not None
    assert contrast_ratio(body_fg, body_bg) >= 4.5
    assert contrast_ratio(link_fg, body_bg) >= 3.0
    assert contrast_ratio(button_fg, button_bg) >= 4.5
