"""CyberOS contract/security smoke tests, run without a Frappe production site."""
import json
import unittest
from pathlib import Path

from softsystem97.cyberos.logic import (
    KINDS, asset_data, action_data, incident_data, identifier, choice,
)

ROOT = Path(__file__).resolve().parents[1]


class CyberOSContracts(unittest.TestCase):
    def test_asset_categories(self):
        self.assertEqual(len(KINDS), 6)
        obj = asset_data(" Serveur 1 ", "SERVER", "CRITICAL", "Facturation")
        self.assertEqual(obj["label"], "Serveur 1")

    def test_no_credentials_in_text(self):
        for value in ("password=123456", "api_key:abc", "private key=abc", "token=secret"):
            with self.assertRaises(ValueError):
                incident_data("Test", "HIGH", value)

    def test_reject_other_fields_and_invalid_urgency(self):
        with self.assertRaises(ValueError):
            asset_data("X", "INTERNAL-EXPLOIT", "HIGH", "Compta")
        with self.assertRaises(ValueError):
            action_data("X", "ACCESS", "SUPERCRITICAL")
        with self.assertRaises(ValueError):
            incident_data("X", "CRITICAL", "")

    def test_uuid_only(self):
        good = "12345678-1234-4234-8234-abcdef123456"
        self.assertEqual(identifier(good), good)
        for bad in ("../other-company", "invalid", good.upper(), "", "1234"):
            with self.assertRaises(ValueError):
                identifier(bad)

    def test_no_client_verified_state(self):
        with self.assertRaises(ValueError):
            choice("VERIFIED", ("OPEN", "IN_PROGRESS", "DONE_DECLARED"))

    def test_doctypes_private_and_tenant_scoped(self):
        for slug in ("asset", "action", "incident"):
            file = ROOT / "softsystem97/softsystem97/doctype" / f"ss97_cyber_{slug}" / f"ss97_cyber_{slug}.json"
            content = json.loads(file.read_text(encoding="utf-8"))
            self.assertEqual(content["permissions"], [{"role": "System Manager", "read": 1, "report": 1}])
            self.assertIn("customer", content["field_order"])
            self.assertEqual(content["module"], "SoftSystem97")

    def test_portal_uses_safe_text_and_not_html(self):
        js = (ROOT / "softsystem97/public/js/ss97_cyberos.js").read_text()
        self.assertIn("textContent", js)
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("sk_live_", js)
        api = (ROOT / "softsystem97/cyberos/api.py").read_text()
        self.assertIn('client_customer_for_user(user)', api)
        self.assertIn('doc.customer != customer', api)
        self.assertIn('frappe.conf.get("ss97_cyberos")', api)
        self.assertNotIn("stripe_client", api)


if __name__ == "__main__":
    unittest.main()
