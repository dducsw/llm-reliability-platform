"""Prompt synthetic tiếng Việt từ template + từ điển sản phẩm hư cấu (không PII)."""

from __future__ import annotations

import random


def make_prompt(route: str, rng: random.Random) -> list[dict]:
    raise NotImplementedError
