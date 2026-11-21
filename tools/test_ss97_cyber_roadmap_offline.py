"""Offline regression tests for phased CyberExpert 360 security advice."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from softsystem97.cyber_assessment.catalog import QUESTIONS
from softsystem97.cyber_assessment.recommendations import roadmap
from softsystem97.cyber_assessment.report import report_html

def fixture(value):
    return {key: value for key in QUESTIONS}

class CyberRoadmapTests(unittest.TestCase):
    def test_yes_only_has_followup(self):
        self.assertEqual(len(roadmap(fixture("YES"))), 1)

    def test_no_is_priority_thirty_days(self):
        values = fixture("YES")
        values["backup"] = "NO"
        self.assertEqual(roadmap(values)[0]["period"], "0–30 jours")

    def test_unknown_requests_confirmation(self):
        values = fixture("YES")
        values["network"] = "UNKNOWN"
        self.assertIn("Confirmer", roadmap(values)[0]["action"])

    def test_partial_is_sixty_days(self):
        values = fixture("YES")
        values["mfa"] = "PARTIAL"
        self.assertEqual(roadmap(values)[0]["period"], "31–60 jours")

    def test_invalid_answer_rejected(self):
        values = fixture("YES")
        values["mfa"] = "INVALID"
        with self.assertRaises(ValueError):
            roadmap(values)

    def test_pdf_escapes_user_text_and_has_roadmap(self):
        doc = SimpleNamespace(name="CYB-001", ticket="ISS-01",
            organization="<script>alert(1)</script>", tier="ESSENTIEL",
            price_eur="100.00", state="RECEIVED")
        profile = dict(sector="<img src=x>", city="Les Abymes",
            country="France", employees="1-10", sites=1, devices=5,
            contact_role="Direction", data_type="CLIENT")
        output = report_html(doc, profile, fixture("NO"))
        self.assertIn("Feuille de route indicative", output)
        self.assertIn("61–90 jours", output)
        self.assertIn("&lt;script&gt;", output)
        self.assertNotIn("<script>", output)

    def test_frontend_does_not_use_html_injection(self):
        root = Path(__file__).resolve().parents[1] / "softsystem97"
        js = (root / "public/js/ss97_cyber_wizard.js").read_text()
        self.assertNotIn("innerHTML", js)
        self.assertIn("textContent", js)
        self.assertIn("reportValidity()", js)
        page = (root / "www/ss97-cyber-entreprises.html").read_text()
        self.assertIn("ss97_cyber_wizard.js", page)
        self.assertIn("ss97_cyber_wizard.css", page)

if __name__ == "__main__":
    unittest.main()
