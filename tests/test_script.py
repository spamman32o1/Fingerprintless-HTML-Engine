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

    variant = script.build_variant(rng, "<p>Example</p>", opt, 1, "en", "title")
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

    variant = script.build_variant(rng, "<p>Meta test</p>", opt, 1, "en", "title")

    head_content = variant.split("<head>", 1)[1].split("</head>", 1)[0]
    meta_tags = re.findall(r"<meta[^>]+>", head_content)

    assert len(meta_tags) >= 3
    assert meta_tags[0] == '<meta charset="utf-8" />'
    assert meta_tags[1] == '<meta name="viewport" content="width=device-width, initial-scale=1" />'
    assert meta_tags[2] == '<meta name="x-apple-disable-message-reformatting" />'


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
    wrapped = script.span_wrap_html(rng, html_in, opt)

    attrs = re.search(r"<p ([^>]+)>", wrapped).group(1).split()

    assert attrs == ['data-flag="true"', 'class="second"', 'id="first"']
