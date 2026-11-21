"""CyberOS v2: pure functions and isolation-guard contract tests."""
import json
import unittest
from pathlib import Path
from softsystem97.cyberos.advanced_logic import (
    dependency_data, continuity_data, drill_data, executive_summary,
)
ROOT = Path(__file__).resolve().parents[1]


class CyberOSV2Tests(unittest.TestCase):
    def test_dependency_requires_two_distinct_uuid(self):
        a = "12345678-1234-4234-8234-abcdef123456"
        b = "12345678-1234-4234-8234-abcdef123457"
        self.assertEqual(dependency_data(a, b, "Facturation")["target_asset"], b)
        with self.assertRaises(ValueError): dependency_data(a, a, "Double")
        with self.assertRaises(ValueError): dependency_data(a, "autre-tenant", "Double")

    def test_continuity_scenario(self):
        self.assertEqual(continuity_data("Facturation", "CYCLONE", "HIGH",
            "Utiliser la sauvegarde hors site", "Direction")["scenario"], "CYCLONE")
        with self.assertRaises(ValueError):
            continuity_data("Test", "HACK_REMOTE", "HIGH", "Aucun", "Direction")

    def test_passwords_rejected(self):
        with self.assertRaises(ValueError):
            continuity_data("Test", "POWER", "HIGH", "password=topsecret", "Direction")

    def test_drill_validation(self):
        self.assertEqual(drill_data("OUTAGE", "Exercer l'équipe")["scenario"], "OUTAGE")
        with self.assertRaises(ValueError): drill_data("EXPLOIT", "Test")

    def test_executive_not_certified(self):
        report = executive_summary(
            [{"criticality":"HIGH"},{"criticality":"LOW"}],
            [{"state":"VERIFIED"},{"state":"OPEN"}],
            [{"state":"REPORTED"}], [], [], [])
        self.assertEqual(report["high_criticality_assets"],1)
        self.assertEqual(report["verified_actions"],1)
        self.assertEqual(report["open_incidents"],1)
        self.assertNotIn("certification", report)
        self.assertTrue(report["warnings"])

    def test_doctypes_private(self):
        for slug in ("dependency","continuity","drill"):
            p = ROOT / "softsystem97/softsystem97/doctype" / ("ss97_cyber_"+slug) / ("ss97_cyber_"+slug+".json")
            value=json.loads(p.read_text())
            self.assertEqual(value["permissions"],[{"role":"System Manager","read":1,"report":1}])
            self.assertIn("customer",value["field_order"])

    def test_browser_safe_and_customer_isolation_check(self):
        js=(ROOT/"softsystem97/public/js/ss97_cyberos_v2.js").read_text()
        self.assertNotIn("innerHTML",js)
        self.assertIn("textContent",js)
        api=(ROOT/"softsystem97/cyberos/advanced_api.py").read_text()
        self.assertIn('_owned(ASSET, data["source_asset"], customer)',api)
        self.assertIn('_owned(ASSET, data["target_asset"], customer)',api)
        self.assertIn('_company()',api)
        self.assertNotIn("stripe_client",api)


if __name__ == "__main__":
    unittest.main()
