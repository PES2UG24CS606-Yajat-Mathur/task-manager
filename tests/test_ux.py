"""
Responsive and accessible UI - TC-UX-01 (TMA-NF-005).

These are automated checks of the HTML and CSS the browser receives. The manual part of
TC-UX-01 (phone width in the browser's dev tools, keyboard-only use with Tab) is in the
Sprint 2 review checklist.
"""

import re
from html.parser import HTMLParser
from pathlib import Path

from tests.helpers import APITestCase

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


class _FormAudit(HTMLParser):
    """Collect form controls, which of them have labels, and the viewport meta tag."""

    def __init__(self):
        super().__init__()
        self.controls, self.label_for, self.viewport = [], set(), False
        self._label_depth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and a.get("name") == "viewport":
            self.viewport = "width=device-width" in a.get("content", "")
        if tag == "label":
            self._label_depth += 1
            if a.get("for"):
                self.label_for.add(a["for"])
        if tag in ("input", "select", "textarea") and a.get("type") != "hidden":
            # labelled by <label for=id>, by an enclosing <label>, or by aria-label
            self.controls.append((a.get("id"), "aria-label" in a or self._label_depth > 0))

    def handle_endtag(self, tag):
        if tag == "label":
            self._label_depth -= 1


def _css_vars(block: str) -> dict:
    """'--ink: #1d2b33;' lines -> {'ink': '#1d2b33'}"""
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", block))


def _contrast(hex1: str, hex2: str) -> float:
    """WCAG 2 contrast ratio between two colours (1 = none, 21 = black on white)."""
    def luminance(hex_colour):
        rgb = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    hi, lo = sorted((luminance(hex1), luminance(hex2)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class TestUsability(APITestCase):
    def page(self):
        with self.client.get("/") as resp:
            self.assertEqual(resp.status_code, 200)
            return resp.get_data(as_text=True)

    def test_TC_UX_01_responsive_and_every_control_is_labelled(self):
        audit = _FormAudit()
        audit.feed(self.page())
        self.assertTrue(audit.viewport, "missing responsive viewport meta tag")
        unlabelled = [cid for cid, wrapped in audit.controls
                      if not wrapped and cid not in audit.label_for]
        self.assertEqual(unlabelled, [], f"controls without a label: {unlabelled}")

        css = (STATIC / "styles.css").read_text(encoding="utf-8")
        for needle in ("@media (max-width", ":focus-visible", "prefers-reduced-motion",
                       "prefers-color-scheme: dark", "min-height: 2.75rem"):
            with self.subTest(css=needle):
                self.assertIn(needle, css)

    def test_text_colours_meet_wcag_aa_contrast_in_both_themes(self):
        css = (STATIC / "styles.css").read_text(encoding="utf-8")
        light = _css_vars(css.split("@media (prefers-color-scheme: dark)")[0])
        dark = {**light, **_css_vars(css.split("@media (prefers-color-scheme: dark)")[1]
                                     .split("}")[0])}
        pairs = [("ink", "paper"), ("muted", "paper"), ("pen", "paper"), ("high", "paper"),
                 ("ink", "surface"), ("pen-ink", "pen")]
        for theme, colours in (("light", light), ("dark", dark)):
            for fg, bg in pairs:
                with self.subTest(theme=theme, fg=fg, bg=bg):
                    self.assertGreaterEqual(_contrast(colours[fg], colours[bg]), 4.5)

    def test_status_messages_are_announced_and_skip_link_exists(self):
        html = self.page()
        self.assertIn('id="toast" class="toast" role="status" aria-live="polite"', html)
        self.assertIn('class="skip-link" href="#main"', html)
        self.assertIn('id="main"', html)
        self.assertRegex(html, r'<html lang="en">')

    def test_dialogs_and_tables_are_named(self):
        html = self.page()
        for dialog_id in re.findall(r'<dialog id="([\w-]+)"', html):
            with self.subTest(dialog=dialog_id):
                self.assertRegex(html, rf'<dialog id="{dialog_id}" aria-labelledby="[\w-]+"')
        self.assertEqual(html.count("<table>"), html.count("<caption"))

    def test_static_assets_served(self):
        for path in ("/static/app.js", "/static/styles.css"):
            with self.subTest(path=path), self.client.get(path) as resp:
                self.assertEqual(resp.status_code, 200)
