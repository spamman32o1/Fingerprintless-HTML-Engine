import json
import random
import re

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import script


SCRIPT_RE = re.compile(r"<script type=\"application/ld\+json\">(.*?)</script>", re.DOTALL)


def _extract_scripts(html_in: str) -> list[str]:
    return SCRIPT_RE.findall(html_in)


def _assert_guardrails(script_text: str) -> None:
    assert len(script_text.encode("utf-8")) <= 200
    json.loads(script_text)

    lower = script_text.lower()
    assert "@type" not in lower
    assert "schema.org" not in lower

    for url in re.findall(r"https?://[^\s\"'>]+", script_text):
        assert url.endswith(".invalid")

    assert not script.FORBIDDEN_BRAND_RE.search(script_text)


def test_build_fake_jsonld_scripts_constraints() -> None:
    rng = random.Random(1234)
    html_block = script.build_fake_jsonld_scripts(rng)

    scripts = _extract_scripts(html_block)
    assert 0 <= len(scripts) <= 2

    for payload in scripts:
        _assert_guardrails(payload)


def test_scripts_inserted_before_body_and_valid() -> None:
    rng = random.Random(7)
    opt = script.Opt(count=1, seed=0)

    variant = script.build_variant(rng, "<p>Example</p>", opt, 1, "en", "title", [])
    scripts = _extract_scripts(variant)

    body_index = variant.index("<body>")
    head_end_index = variant.index("</head>")
    assert head_end_index < body_index

    for match in SCRIPT_RE.finditer(variant):
        assert match.start() < head_end_index

    for payload in scripts:
        _assert_guardrails(payload)


def test_build_variant_includes_required_meta_tags() -> None:
    rng = random.Random(9)
    opt = script.Opt(count=1, seed=0)

    variant = script.build_variant(rng, "<p>Meta test</p>", opt, 1, "en", "title", [])

    head_content = variant.split("<head>", 1)[1].split("</head>", 1)[0]
    meta_tags = re.findall(r"<meta[^>]+>", head_content)

    assert len(meta_tags) >= 3
    assert meta_tags[0] == '<meta charset="utf-8" />'
    assert meta_tags[1] == '<meta name="viewport" content="width=device-width, initial-scale=1" />'
    assert meta_tags[2] == '<meta name="x-apple-disable-message-reformatting" content="yes" />'


def test_span_wrap_reorders_attributes() -> None:
    rng = random.Random(21)
    opt = script.Opt(
        count=1,
        seed=0,
        wrap_chunk_rate=0.0,
        chunk_len_min=1,
        chunk_len_max=1,
        per_word_rate=0.0,
        noise_divs_max=0,
    )

    html_in = '<p id="first" class="second" data-flag="true">Hello</p>'
    wrapped = script.span_wrap_html(rng, html_in, opt, [])

    attrs = re.search(r"<p ([^>]+)>", wrapped).group(1).split()

    assert attrs == ['data-flag="true"', 'class="second"', 'id="first"']


def test_replace_cellspacing_with_css() -> None:
    html_in = '<table cellspacing="6" class="promo"><tr><td>Hi</td></tr></table>'
    updated = script.replace_cellspacing_with_css(html_in)

    assert 'cellspacing="6"' not in updated
    assert 'style="border-spacing:6;"' in updated
    assert '<table class="promo" style="border-spacing:6;">' in updated


def test_normalize_center_tags_to_divs() -> None:
    html_in = "<center>Hi</center>"
    updated = script.normalize_input_html(html_in)

    assert "<center>" not in updated
    assert "</center>" not in updated
    assert updated == '<div style="text-align:center;">Hi</div>'


def test_normalize_table_and_cell_attrs_to_styles() -> None:
    html_in = (
        '<table border="1" cellpadding="4" width="600" align="center">'
        '<tr><td border="2" cellpadding="3" width="200" align="right">Hi</td></tr>'
        "</table>"
    )
    updated = script.normalize_input_html(html_in)

    assert 'border="1"' not in updated
    assert 'cellpadding="4"' not in updated
    assert 'width="600"' not in updated
    assert 'align="center"' not in updated
    assert 'border="2"' not in updated
    assert 'cellpadding="3"' not in updated
    assert 'width="200"' not in updated
    assert 'align="right"' not in updated
    assert "border:1px solid;" in updated
    assert "padding:4px;" in updated
    assert "width:600px;" in updated
    assert "text-align:center;" in updated
    assert "border:2px solid;" in updated
    assert "padding:3px;" in updated
    assert "width:200px;" in updated
    assert "text-align:right;" in updated
