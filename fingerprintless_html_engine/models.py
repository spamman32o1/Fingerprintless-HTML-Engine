from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Opt:
    count: int

    wrap_chunk_rate: float = 0.027
    chunk_len_min: int = 2
    chunk_len_max: int = 6

    per_word_rate: float = 0.0033

    noise_divs_max: int = 4
    max_nesting: int = 4
    title_prefix: str = "Variant"

    meta_noise_min: int = 4
    meta_noise_max: int = 14

    ie_condition_randomize: bool = True
    structure_randomize: bool = True


@dataclass
class _HtmlNode:
    tag: str | None
    open_tag: str
    close_tag: str | None
    children: list["_HtmlNode"]
    text: str
    self_closing: bool = False

    def render(self) -> str:
        if self.tag is None:
            return self.text
        inner = "".join(child.render() for child in self.children)
        close = "" if self.self_closing else (self.close_tag or "")
        return f"{self.open_tag}{inner}{close}"
