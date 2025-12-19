from __future__ import annotations

import random
import re

from .constants import SAFE_WRAPPER_TAGS, SKIP_TEXT_INSIDE, TAG_SPLIT_RE, VOID_ELEMENTS
from .models import _HtmlNode
from .random_utils import maybe, pick


def _tag_name(tag_text: str) -> str | None:
    m = re.match(r"^</?\s*([a-zA-Z0-9:_-]+)", tag_text)
    if not m:
        return None
    return m.group(1).lower()


def _is_safe_wrapper(tag_text: str, tag_name: str | None) -> bool:
    if not tag_name or tag_name not in SAFE_WRAPPER_TAGS:
        return False
    m = re.match(r"^<\s*[a-zA-Z0-9:_-]+([^>]*)>$", tag_text)
    if not m:
        return False
    rest = m.group(1)
    return rest.strip() in {"", "/"}


def _is_wrapper_tag(tag_name: str | None) -> bool:
    return bool(tag_name and tag_name in SAFE_WRAPPER_TAGS)


def _replace_tag_name(tag_text: str | None, new_tag: str) -> str | None:
    if not tag_text:
        return tag_text
    if tag_text.startswith("</"):
        return re.sub(r"^</\s*[a-zA-Z0-9:_-]+", f"</{new_tag}", tag_text, count=1, flags=re.IGNORECASE)
    return re.sub(r"^<\s*[a-zA-Z0-9:_-]+", f"<{new_tag}", tag_text, count=1, flags=re.IGNORECASE)


def _make_wrapper_node(tag_name: str, child: _HtmlNode) -> _HtmlNode:
    return _HtmlNode(
        tag=tag_name,
        open_tag=f"<{tag_name}>",
        close_tag=f"</{tag_name}>",
        children=[child],
        text="",
    )


def _parse_html_nodes(html_in: str) -> _HtmlNode:
    parts = TAG_SPLIT_RE.split(html_in)
    root = _HtmlNode(tag="__root__", open_tag="", close_tag="", children=[], text="")
    stack = [root]

    for part in parts:
        if not part:
            continue

        if part.startswith("<") and part.endswith(">"):
            if part.startswith("</"):
                name = _tag_name(part)
                if name and len(stack) > 1 and stack[-1].tag == name:
                    stack[-1].close_tag = part
                    stack.pop()
                else:
                    stack[-1].children.append(_HtmlNode(None, "", None, [], part))
                continue

            if part.startswith("<!") or part.startswith("<?"):
                stack[-1].children.append(_HtmlNode(None, "", None, [], part))
                continue

            name = _tag_name(part)
            if not name:
                stack[-1].children.append(_HtmlNode(None, "", None, [], part))
                continue

            is_self_closing = part.rstrip().endswith("/>") or name in VOID_ELEMENTS
            node = _HtmlNode(tag=name, open_tag=part, close_tag=None, children=[], text="", self_closing=is_self_closing)
            stack[-1].children.append(node)
            if not is_self_closing:
                stack.append(node)
            continue

        stack[-1].children.append(_HtmlNode(None, "", None, [], part))

    return root


def _shuffle_safe_siblings(rng: random.Random, node: _HtmlNode) -> None:
    if node.tag in SKIP_TEXT_INSIDE:
        return

    shuffle_indices = [
        idx
        for idx, child in enumerate(node.children)
        if child.tag is not None and _is_safe_wrapper(child.open_tag, child.tag)
    ]
    if len(shuffle_indices) > 1:
        shuffled = [node.children[idx] for idx in shuffle_indices]
        rng.shuffle(shuffled)
        for idx, child in zip(shuffle_indices, shuffled):
            node.children[idx] = child

    for child in node.children:
        if child.tag is not None:
            _shuffle_safe_siblings(rng, child)


def _maybe_wrap_child(rng: random.Random, child: _HtmlNode) -> _HtmlNode:
    if child.tag is not None and child.tag in SKIP_TEXT_INSIDE:
        return child
    if maybe(rng, 0.03):
        return _make_wrapper_node(pick(rng, sorted(SAFE_WRAPPER_TAGS)), child)
    return child


def _maybe_swap_wrapper_tag(rng: random.Random, node: _HtmlNode) -> None:
    if not _is_wrapper_tag(node.tag):
        return
    if node.self_closing:
        return
    if not maybe(rng, 0.04):
        return
    options = [tag for tag in sorted(SAFE_WRAPPER_TAGS) if tag != node.tag]
    if not options:
        return
    new_tag = pick(rng, options)
    node.tag = new_tag
    node.open_tag = _replace_tag_name(node.open_tag, new_tag) or node.open_tag
    if node.close_tag:
        node.close_tag = _replace_tag_name(node.close_tag, new_tag) or node.close_tag


def _maybe_jitter_wrapper_depth(rng: random.Random, parent: _HtmlNode, idx: int) -> None:
    if not maybe(rng, 0.02):
        return
    child = parent.children[idx]
    if not _is_wrapper_tag(child.tag):
        return
    if child.tag in SKIP_TEXT_INSIDE:
        return
    if len(child.children) != 1:
        return
    only_child = child.children[0]
    if only_child.tag is None:
        return
    if only_child.tag in SKIP_TEXT_INSIDE:
        return
    if only_child.tag in VOID_ELEMENTS or only_child.self_closing:
        return
    child.children = only_child.children
    only_child.children = [child]
    parent.children[idx] = only_child


def _mutate_safe_structure(rng: random.Random, node: _HtmlNode) -> None:
    if node.tag in SKIP_TEXT_INSIDE:
        return

    _shuffle_safe_siblings(rng, node)

    idx = 0
    while idx < len(node.children):
        child = node.children[idx]
        if child.tag is not None:
            wrapped = _maybe_wrap_child(rng, child)
            if wrapped is not child:
                node.children[idx] = wrapped
                child = wrapped
            _maybe_jitter_wrapper_depth(rng, node, idx)
            if node.children[idx] is not child:
                child = node.children[idx]
            _maybe_swap_wrapper_tag(rng, child)
            _mutate_safe_structure(rng, child)
        idx += 1


def randomize_structure(rng: random.Random, content_html: str, enabled: bool) -> str:
    if not enabled:
        return content_html

    root = _parse_html_nodes(content_html)
    _mutate_safe_structure(rng, root)
    return "".join(child.render() for child in root.children)
