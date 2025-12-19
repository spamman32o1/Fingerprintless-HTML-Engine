import json
import random
import re

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
