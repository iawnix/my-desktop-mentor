from __future__ import annotations

import builtins
import unittest

from desktop_mentor_app.ui.markdown_rendering import render_markdown_fragment


class MarkdownRenderingTests(unittest.TestCase):
    def test_parenthesized_inline_math_is_extracted(self) -> None:
        rendered = render_markdown_fragment(r"Inline \(E=mc^2\) text")

        self.assertIn("math-inline", rendered)
        self.assertNotIn(r"\(", rendered)

    def test_bracketed_block_math_is_extracted(self) -> None:
        rendered = render_markdown_fragment(r"\[\int_0^1 x^2 dx = \frac{1}{3}\]")

        self.assertIn("math-block", rendered)
        self.assertNotIn(r"\[", rendered)

    def test_table_after_list_intro_is_rendered_as_table(self) -> None:
        rendered = render_markdown_fragment("- 表格：\n| 参数 | 值 |\n|---|---|\n| a | 1 |")

        self.assertIn("<table>", rendered)
        self.assertNotIn("|---|", rendered)

    def test_fallback_renderer_supports_tables(self) -> None:
        original_import = builtins.__import__

        def blocked_markdown_it_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "markdown_it" or name.startswith("markdown_it."):
                raise ModuleNotFoundError(name)
            return original_import(name, globals, locals, fromlist, level)

        builtins.__import__ = blocked_markdown_it_import
        try:
            rendered = render_markdown_fragment("| 参数 | 值 |\n|---|---|\n| a | 1 |")
        finally:
            builtins.__import__ = original_import

        self.assertIn("<table>", rendered)
        self.assertNotIn("|---|", rendered)


if __name__ == "__main__":
    unittest.main()
