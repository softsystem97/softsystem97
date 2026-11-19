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

    def test_visibility_control_in_synthetic_dom(self):
        test_script = ROOT / "tools/test_password_visibility.cjs"
        result = subprocess.run(
            ["node", str(test_script)], cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Password contrast controls OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
