"""Offline checks for SS97 password readability, without real credentials."""

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestPasswordContrast(unittest.TestCase):
    def test_stylesheet_loaded_on_portal_and_desk(self):
        import sys

        sys.path.insert(0, str(ROOT))
        from softsystem97 import hooks

        sheet = "/assets/softsystem97/css/password-contrast.css"
        self.assertIn(sheet, hooks.web_include_css)
        self.assertIn(sheet, hooks.app_include_css)
        self.assertIn(
            "/assets/softsystem97/css/portal-contrast.css", hooks.web_include_css
        )
        self.assertNotIn(
            "/assets/softsystem97/css/portal-contrast.css", hooks.app_include_css
        )
        self.assertIn(
            "/assets/softsystem97/js/password-visibility.js", hooks.web_include_js
        )

    def test_password_foreground_and_background_always_paired(self):
        css = (ROOT / "softsystem97/public/css/password-contrast.css").read_text()
        self.assertIn('input[type="password"]', css)
        self.assertIn('input[data-ss97-password-visible="true"]', css)
        self.assertIn("background-color: #f7fbff !important", css)
        self.assertIn("color: #142b3e !important", css)
        self.assertIn("-webkit-text-fill-color: #142b3e !important", css)
        self.assertIn(":-webkit-autofill", css)

    def test_portal_contrast_covers_login_fields_and_low_contrast_buttons(self):
        css = (ROOT / "softsystem97/public/css/portal-contrast.css").read_text()
        for selector in (
            'input[type="text"]',
            'input[type="email"]',
            'input[type="tel"]',
            'input[type="search"]',
            'input[type="number"]',
            "textarea",
            "select",
            ".ss97-tl-assist a",
            ".ss-btn-contour",
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, css)
        self.assertNotIn('input[type="checkbox"]', css)
        self.assertNotIn('input[type="radio"]', css)

        def luminance(hex_color):
            channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
            linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
            return sum(a * b for a, b in zip(linear, (0.2126, 0.7152, 0.0722)))

        def contrast(a, b):
            x, y = sorted((luminance(a), luminance(b)), reverse=True)
            return (x + 0.05) / (y + 0.05)

        # Reproduced from the live technician-login computed styles, 19 Nov 2026.
        self.assertLess(contrast("#0f172a", "#07111d"), 1.5)
        for foreground, background in (
            ("#142b3e", "#f7fbff"),
            ("#4c6577", "#f7fbff"),
            ("#e5f7ff", "#0c2846"),
            ("#8be7ff", "#07111d"),
        ):
            with self.subTest(foreground=foreground):
                self.assertGreaterEqual(contrast(foreground, background), 4.5)

    def test_visibility_control_in_synthetic_dom(self):
        test_script = ROOT / "tools/test_password_visibility.cjs"
        result = subprocess.run(
            ["node", str(test_script)], cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Password contrast controls OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
