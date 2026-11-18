"""Public-facing safety contracts for the TECH OS and cyber pilot UI.

These fast checks do not replace authenticated Frappe integration tests.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1] / "softsystem97"


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


class PublicUiContracts(unittest.TestCase):
    def test_admin_controls_wait_for_server_authorization(self):
        html = source("www/ss97-tech-admin.html")
        js = source("public/js/ss97_tech_admin.js")
        self.assertIn('<div id="admin-protected" hidden>', html)
        self.assertLess(html.index('id="admin-protected"'),
                        html.index('id="admin-review-form"'))
        self.assertLess(js.index('await api("get_admin_overview")'),
                        js.index('$("admin-protected").hidden = false'))

    def test_candidate_entry_explains_separate_recruitment(self):
        html = source("www/ss97-tech-os.html")
        self.assertIn('href="/recrutement"', html)
        self.assertIn('href="/login?redirect-to=%2Fss97-tech-os#signup"', html)
        self.assertIn("Une candidature générale ne crée pas automatiquement", html)

    def test_cyber_submit_remains_disabled_before_approval(self):
        html = source("www/ss97-cyber-entreprises.html")
        js = source("public/js/ss97_cyber_enterprises.js")
        self.assertIn('id="cyber-submit" type="submit" disabled', html)
        self.assertIn('catalogActive = payload.active === true', js)
        self.assertIn('if (!catalogActive)', js)
        self.assertIn('finally {button.disabled = !catalogActive;}', js)

    def test_headings_remain_legible_on_dark_site_theme(self):
        for file in ("public/css/ss97_tech_universe.css", "www/ss97-tech-os.html"):
            with self.subTest(file=file):
                css = source(file)
                self.assertIn("background:#f7f9fc", css)
                self.assertIn("color:#162b43", css)


if __name__ == "__main__":
    unittest.main()
