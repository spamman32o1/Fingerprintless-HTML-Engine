from __future__ import annotations

import random


def pick(rng: random.Random, xs):
    return xs[rng.randrange(len(xs))]


def _clamp_rate(val: float) -> float:
    return max(0.0, min(1.0, val))


def rfloat(rng: random.Random, a: float, b: float, digits: int = 3) -> float:
    return round(rng.uniform(a, b), digits)


def rint(rng: random.Random, a: int, b: int) -> int:
    return rng.randint(a, b)


def maybe(rng: random.Random, p: float) -> bool:
    return rng.random() < p
