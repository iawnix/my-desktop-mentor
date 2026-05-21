"""Markdown rendering helpers for chat replies."""
from __future__ import annotations

import html
import re
from collections.abc import Callable

from .tokens import FLUENT_DARK_COLORS

MathReplacement = tuple[str, str, bool]

_FENCE_RE = re.compile(r"^\s{0,3}(```+|~~~+)")
_INLINE_FENCE_RE = re.compile(r"(?<!\n)(```+|~~~+)")
_FENCE_WITH_SAME_LINE_CODE_RE = re.compile(
    r"(```+|~~~+)([A-Za-z0-9_+.#-]{1,32})[ \t]+(?=\S)"
)
_FENCE_WITH_SAME_LINE_TEXT_RE = re.compile(r"(```+|~~~+)[ \t]+(?=\S)")
_BLOCK_MATH_RE = re.compile(r"(?<!\\)\$\$(.+?)(?<!\\)\$\$", re.DOTALL)
_BRACKET_MATH_RE = re.compile(r"(?<!\\)\\\[(.+?)(?<!\\)\\\]", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"(?<!\\)\$(?![\s$])(.+?)(?<![\s\\])\$(?!\d)", re.DOTALL)
_PAREN_MATH_RE = re.compile(r"(?<!\\)\\\((.+?)(?<!\\)\\\)", re.DOTALL)


def _is_table_separator(line: str) -> bool:
    stripped = line.strip().strip("|")
    if "|" not in line or not stripped:
        return False
    cells = [cell.strip() for cell in stripped.split("|")]
    return len(cells) >= 2 and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)


def _looks_like_table_row(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and "|" in stripped and not _FENCE_RE.match(stripped)


def _split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _highlight_code(code: str, language: str, _attrs: str = "") -> str:
    lang = (language or "").strip().split(maxsplit=1)[0]
    label = html.escape(lang) if lang else "text"
    try:
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import TextLexer, get_lexer_by_name

        lexer = get_lexer_by_name(lang) if lang else TextLexer()
        formatter = HtmlFormatter(nowrap=True, noclasses=True)
        highlighted = highlight(code, lexer, formatter)
    except Exception:
        highlighted = html.escape(code)
    return (
        '<pre class="codehilite">'
        f'<div class="code-lang">{label}</div>'
        f"<code>{highlighted}</code>"
        "</pre>"
    )


def _math_to_html(source: str, display: bool) -> str:
    expression = source.strip()
    try:
        from latex2mathml import converter

        try:
            mathml = converter.convert(expression, display=display)
        except TypeError:
            mathml = converter.convert(expression)
        if display:
            mathml = mathml.replace('display="inline"', 'display="block"', 1)
        if display:
            return f'<div class="math math-block">{mathml}</div>'
        return f'<span class="math math-inline">{mathml}</span>'
    except Exception:
        escaped = html.escape(expression)
        if display:
            return f'<div class="math math-block math-source"><code>{escaped}</code></div>'
        return f'<span class="math math-inline math-source"><code>{escaped}</code></span>'


def normalize_model_markdown(markdown: str) -> str:
    normalized = str(markdown or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if "```" in normalized or "~~~" in normalized:
        normalized = _INLINE_FENCE_RE.sub(r"\n\1", normalized)
        normalized = _FENCE_WITH_SAME_LINE_CODE_RE.sub(r"\1\2\n", normalized)
        normalized = _FENCE_WITH_SAME_LINE_TEXT_RE.sub(r"\1\n", normalized)
    return _normalize_model_tables(normalized).strip()


def _normalize_model_tables(markdown: str) -> str:
    lines = markdown.split("\n")
    normalized: list[str] = []
    in_fence: str | None = None
    for index, line in enumerate(lines):
        fence_match = _FENCE_RE.match(line)
        if in_fence:
            normalized.append(line)
            if fence_match and fence_match.group(1).startswith(in_fence):
                in_fence = None
            continue
        if fence_match:
            in_fence = fence_match.group(1)[0]
            normalized.append(line)
            continue
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        starts_table = _looks_like_table_row(line) and _is_table_separator(next_line)
        if starts_table and normalized and normalized[-1].strip() and not _looks_like_table_row(normalized[-1]):
            normalized.append("")
        normalized.append(line)
    return "\n".join(normalized)


def _replace_math_in_text(text: str, add_replacement: Callable[[str, bool], str]) -> str:
    def block_replacer(match: re.Match[str]) -> str:
        return add_replacement(match.group(1), True)

    def inline_replacer(match: re.Match[str]) -> str:
        return add_replacement(match.group(1), False)

    text = _BLOCK_MATH_RE.sub(block_replacer, text)
    text = _BRACKET_MATH_RE.sub(block_replacer, text)
    text = _INLINE_MATH_RE.sub(inline_replacer, text)
    return _PAREN_MATH_RE.sub(inline_replacer, text)


def _render_inline_fallback(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


def _flush_paragraph(lines: list[str], blocks: list[str]) -> None:
    if not lines:
        return
    paragraph = " ".join(line.strip() for line in lines if line.strip())
    if paragraph:
        blocks.append(f"<p>{_render_inline_fallback(paragraph)}</p>")
    lines.clear()


def _render_markdown_fallback(markdown: str) -> str:
    blocks: list[str] = []
    paragraph_lines: list[str] = []
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            _flush_paragraph(paragraph_lines, blocks)
            fence = fence_match.group(1)
            language = line[fence_match.end() :].strip()
            code_lines: list[str] = []
            index += 1
            while index < len(lines):
                end_match = _FENCE_RE.match(lines[index])
                if end_match and end_match.group(1).startswith(fence[0]):
                    break
                code_lines.append(lines[index])
                index += 1
            blocks.append(_highlight_code("\n".join(code_lines), language))
        elif _looks_like_table_row(line) and index + 1 < len(lines) and _is_table_separator(lines[index + 1]):
            _flush_paragraph(paragraph_lines, blocks)
            headers = _split_table_row(line)
            rows: list[list[str]] = []
            index += 2
            while index < len(lines) and _looks_like_table_row(lines[index]):
                rows.append(_split_table_row(lines[index]))
                index += 1
            header_html = "".join(f"<th>{_render_inline_fallback(cell)}</th>" for cell in headers)
            body_html = "".join(
                "<tr>" + "".join(f"<td>{_render_inline_fallback(cell)}</td>" for cell in row) + "</tr>"
                for row in rows
            )
            blocks.append(f"<table><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>")
            continue
        elif not line.strip():
            _flush_paragraph(paragraph_lines, blocks)
        elif line.lstrip().startswith(("- ", "* ")):
            _flush_paragraph(paragraph_lines, blocks)
            items: list[str] = []
            while index < len(lines) and lines[index].lstrip().startswith(("- ", "* ")):
                items.append(f"<li>{_render_inline_fallback(lines[index].lstrip()[2:].strip())}</li>")
                index += 1
            blocks.append(f"<ul>{''.join(items)}</ul>")
            continue
        else:
            paragraph_lines.append(line)
        index += 1
    _flush_paragraph(paragraph_lines, blocks)
    return "\n".join(blocks)


def _extract_math(markdown: str) -> tuple[str, list[MathReplacement]]:
    replacements: list[MathReplacement] = []

    def add_replacement(source: str, display: bool) -> str:
        placeholder = f"MDMENTORMATH{len(replacements):04d}TOKEN"
        replacements.append((placeholder, _math_to_html(source, display), display))
        return placeholder

    chunks: list[tuple[str, str]] = []
    text_lines: list[str] = []
    in_fence: str | None = None

    for line in markdown.splitlines(keepends=True):
        fence_match = _FENCE_RE.match(line)
        if in_fence:
            chunks.append(("raw", line))
            if fence_match and fence_match.group(1).startswith(in_fence):
                in_fence = None
            continue
        if fence_match:
            if text_lines:
                chunks.append(("text", "".join(text_lines)))
                text_lines = []
            in_fence = fence_match.group(1)[0]
            chunks.append(("raw", line))
            continue
        text_lines.append(line)

    if text_lines:
        chunks.append(("text", "".join(text_lines)))

    protected = "".join(
        value if kind == "raw" else _replace_math_in_text(value, add_replacement)
        for kind, value in chunks
    )
    return protected, replacements


def _render_markdown(markdown: str) -> str:
    normalized_markdown = normalize_model_markdown(markdown)
    protected_markdown, math_replacements = _extract_math(normalized_markdown)
    try:
        from markdown_it import MarkdownIt

        renderer = MarkdownIt(
            "gfm-like",
            options_update={
                "breaks": False,
                "html": False,
                "linkify": False,
                "typographer": False,
                "highlight": _highlight_code,
            },
        )
        rendered = renderer.render(protected_markdown)
    except Exception:
        rendered = _render_markdown_fallback(protected_markdown)

    for placeholder, replacement, display in math_replacements:
        if display:
            rendered = rendered.replace(f"<p>{placeholder}</p>", replacement)
        rendered = rendered.replace(placeholder, replacement)
    return rendered


def markdown_css() -> str:
    colors = FLUENT_DARK_COLORS
    return f"""
:root {{
  color-scheme: dark;
}}
html, body {{
  margin: 0;
  padding: 0;
  background: transparent;
}}
body {{
  color: {colors["text_primary"]};
  font-family: "Inter", "Segoe UI", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
  font-size: 13px;
  line-height: 1.46;
  overflow: hidden;
}}
p {{
  margin: 0 0 8px 0;
}}
p:last-child {{
  margin-bottom: 0;
}}
h1, h2, h3, h4 {{
  color: {colors["text_primary"]};
  font-weight: 700;
  line-height: 1.25;
  margin: 8px 0 6px 0;
}}
h1 {{ font-size: 20px; }}
h2 {{ font-size: 17px; }}
h3 {{ font-size: 15px; }}
h4 {{ font-size: 14px; }}
ul, ol {{
  margin: 4px 0 8px 0;
  padding-left: 20px;
}}
li {{
  margin: 2px 0;
}}
blockquote {{
  color: {colors["text_secondary"]};
  border-left: 3px solid {colors["accent"]};
  margin: 6px 0 8px 0;
  padding: 2px 0 2px 10px;
}}
code {{
  color: {colors["text_primary"]};
  background: {colors["surface_control"]};
  border-radius: 4px;
  font-family: "SFMono-Regular", "SF Mono", Consolas, "Liberation Mono", monospace;
  font-size: 12px;
  padding: 1px 4px;
}}
pre.codehilite {{
  background: {colors["input"]};
  border: 1px solid {colors["border_control"]};
  border-radius: 7px;
  margin: 7px 0 9px 0;
  overflow-x: auto;
  padding: 28px 10px 10px 10px;
  position: relative;
  white-space: pre;
}}
pre.codehilite code {{
  background: transparent;
  border-radius: 0;
  color: {colors["text_primary"]};
  display: block;
  font-size: 12px;
  line-height: 1.45;
  padding: 0;
}}
.code-lang {{
  color: {colors["text_subtle"]};
  font-size: 10px;
  font-weight: 650;
  left: 10px;
  letter-spacing: 0;
  position: absolute;
  text-transform: uppercase;
  top: 7px;
}}
a {{
  color: {colors["focus"]};
  text-decoration: none;
}}
a:hover {{
  text-decoration: underline;
}}
table {{
  border-collapse: collapse;
  margin: 6px 0 9px 0;
  width: 100%;
}}
th, td {{
  border: 1px solid {colors["border_control"]};
  padding: 5px 7px;
  vertical-align: top;
}}
th {{
  background: {colors["surface_control"]};
  font-weight: 700;
}}
.math {{
  color: {colors["text_primary"]};
}}
.math-block {{
  background: {colors["input"]};
  border: 1px solid {colors["border_control"]};
  border-radius: 7px;
  margin: 7px 0 9px 0;
  overflow-x: auto;
  padding: 9px 10px;
  text-align: center;
}}
.math-inline {{
  display: inline-block;
  vertical-align: middle;
}}
.math-source code {{
  background: transparent;
  padding: 0;
}}
math {{
  color: {colors["text_primary"]};
  font-size: 15px;
}}
"""


def render_markdown_fragment(markdown: str) -> str:
    return _render_markdown(markdown)


def render_markdown_document(markdown: str) -> str:
    body = render_markdown_fragment(markdown)
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
{markdown_css()}
  </style>
</head>
<body>
{body}
</body>
</html>
"""
