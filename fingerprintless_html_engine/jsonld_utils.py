from __future__ import annotations

import json
import random

from .constants import FORBIDDEN_BRAND_RE, FORBIDDEN_URL_RE, JSONLD_MUTATION_POOL
from .random_utils import pick, rint


def _normalized_json_order(rng: random.Random, val):
    if isinstance(val, dict):
        items = list(val.items())
        rng.shuffle(items)
        return {k: _normalized_json_order(rng, v) for k, v in items}
    if isinstance(val, list):
        return [_normalized_json_order(rng, v) for v in val]
    return val


def _violates_jsonld_guardrails(payload_text: str) -> bool:
    lower = payload_text.lower()
    if "@type" in lower or "schema.org" in lower:
        return True

    if FORBIDDEN_BRAND_RE.search(payload_text):
        return True

    for url in FORBIDDEN_URL_RE.findall(payload_text):
        if not url.endswith(".invalid"):
            return True

    return False


def _serialize_jsonld_payload(rng: random.Random, payload) -> str:
    separators = pick(rng, [(",", ":"), (",", ": "), (", ", ":"), (", ", ": ")])
    base = json.dumps(payload, separators=separators, indent=None)

    pad_left = " " * rint(rng, 0, 2)
    pad_right = " " * rint(rng, 0, 2)
    return f"{pad_left}{base}{pad_right}"


def build_fake_jsonld_scripts(rng: random.Random) -> str:
    n_scripts = rint(rng, 0, 2)
    blocks: list[str] = []

    for _ in range(n_scripts):
        for _ in range(5):
            payload = rng.choice(JSONLD_MUTATION_POOL)
            payload_copy = json.loads(json.dumps(payload))
            normalized = _normalized_json_order(rng, payload_copy)
            json_text = _serialize_jsonld_payload(rng, normalized)

            if len(json_text.encode("utf-8")) > 200:
                continue

            if _violates_jsonld_guardrails(json_text):
                continue

            try:
                json.loads(json_text)
            except json.JSONDecodeError:
                continue

            blocks.append(f'<script type="application/ld+json">{json_text}</script>')
            break

    return "".join(blocks)
