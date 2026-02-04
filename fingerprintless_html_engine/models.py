from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Opt:
    count: int

    wrap_chunk_rate: float = 0.027
    chunk_len_min: int = 2
    chunk_len_max: int = 6

    per_word_rate: float = 0.0033
    enable_wrap_chunk_rate: bool = True
    enable_per_word_rate: bool = True

    noise_divs_max: int = 4
    max_nesting: int = 4
    max_nesting_jitter: int = 0
    title_prefix: str = "Variant"

    ie_condition_randomize: bool = True
    structure_randomize: bool = True
    # "default", "strict", "super_strict", or "libero"
    output_mode: str = "default"
    allow_dark_mode: bool = True
    enable_css_randomization: bool = True
    enable_font_randomization: bool = True
    enable_gradients: bool = True
    enable_noise_textures: bool = True
    enable_color_palette_randomization: bool = True
    enable_font_features: bool = True
    enable_span_wrapping: bool = True
    enable_alt_text_randomization: bool = True
    enable_meta_noise: bool = True
    enable_jsonld_noise: bool = True
    enable_noise_divs: bool = True
    enable_wrapper_nesting: bool = True
    enable_layout_randomization: bool = True


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
