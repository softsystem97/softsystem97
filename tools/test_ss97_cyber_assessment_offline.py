"""Cyber intake unit contracts. No remote scan, mail, client or production write."""

import importlib
import json
import sys
import types
import unittest
from unittest.mock import patch

from softsystem97.cyber_assessment.catalog import TIERS, build_ticket, request_payload


class CyberCatalogTests(unittest.TestCase):
    def test_three_risk_scoped_tiers(self):
        self.assertEqual(set(TIERS), {"ESSENTIEL", "SUPERIEUR", "EXTREME"})
        for spec in TIERS.values():
            self.assertTrue(spec["checks"])
            self.assertTrue(spec["deliverables"])
        self.assertIn("mandat écrit", TIERS["EXTREME"]["description"])

    def test_no_cyber_request_without_consent_or_valid_tier(self):
        cases = [
            ("CYBER", "N4", "Entreprise", "Sécuriser notre réseau", True),
            ("CYBER", "EXTREME", "Entreprise", "Sécuriser notre réseau", False),
            ("LIBRE", "EXTREME", "Entreprise", "Assistance imprimante", True),
            ("LIBRE", "", "Entreprise", "password=unsafe", True),
            ("LIBRE", "", "", "Besoin", True),
            ("LIBRE", "", "Entreprise", "", True),
        ]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                request_payload(*args)

    def test_issue_is_not_an_intervention_authorization(self):
        data = request_payload("CYBER", "EXTREME", " Exemple SA ",
                               " Revue des sauvegardes ", True)
        subject, detail = build_ticket(data)
        self.assertTrue(subject.startswith("[SS97-CYBER] Exemple SA"))
        self.assertIn("Extrême", detail)
        self.assertIn("Aucun test d'intrusion", detail)
        self.assertNotIn("password", detail)

    def test_free_ticket_uses_distinct_marker(self):
        payload = request_payload("LIBRE", "", "École", "PC ralenti", True)
        subject, detail = build_ticket(payload)
        self.assertTrue(subject.startswith("[SS97-LIBRE]"))
        self.assertIn("Ticket libre", detail)


class CyberApiTests(unittest.TestCase):
    def setUp(self):
        self.fake_frappe = types.ModuleType("frappe")
        self.fake_frappe.__path__ = []
        self.fake_frappe.PermissionError = PermissionError
        self.fake_frappe.whitelist = lambda **kwargs: (lambda fn: fn)
        self.fake_frappe.conf = {"ss97_cyber_assessment": {"enabled": True}}
        self.fake_frappe.session = types.SimpleNamespace(user="client@example.test")
        self.fake_frappe.db = types.SimpleNamespace(get_value=lambda *args: 1)
        self.fake_frappe.get_roles = lambda user: ["Customer"]
        self.fake_frappe.throw = lambda msg, kind=ValueError: (_ for _ in ()).throw(kind(msg))
        self.fake_integrations = types.ModuleType("softsystem97.integrations")
        self.fake_integrations.__path__ = []
        self.fake_ticket_bridge = types.ModuleType("softsystem97.integrations.ticket_bridge")
        self.fake_ticket_bridge.__path__ = []
        self.fake_policy = types.ModuleType("softsystem97.integrations.ticket_bridge.policy")
        self.fake_policy.customer = lambda: ("client@example.test", "CLIENT-1")
        self.fake_bridge = types.ModuleType("softsystem97.integrations.ticket_bridge.api")
        self.fake_bridge.create_ticket = lambda s, d, r: {"name": "ISS-TEST-001", "status": "Open"}
        self.fake_ticket_bridge.policy = self.fake_policy
        self.patch_modules = patch.dict(sys.modules, {
            "frappe": self.fake_frappe,
            "softsystem97.integrations": self.fake_integrations,
            "softsystem97.integrations.ticket_bridge": self.fake_ticket_bridge,
            "softsystem97.integrations.ticket_bridge.policy": self.fake_policy,
            "softsystem97.integrations.ticket_bridge.api": self.fake_bridge,
        })
        self.patch_modules.start()
        sys.modules.pop("softsystem97.cyber_assessment.api", None)
        self.api = importlib.import_module("softsystem97.cyber_assessment.api")

    def tearDown(self):
        sys.modules.pop("softsystem97.cyber_assessment.api", None)
        self.patch_modules.stop()

    def test_customer_ticket_reuses_existing_bridge(self):
        result = self.api.request_assessment("CYBER", "SUPERIEUR", "Entreprise",
                                             "Revue des habilitations", True, "r-12345")
        self.assertEqual(result["name"], "ISS-TEST-001")
        self.assertEqual(result["tier"], "SUPERIEUR")

    def test_feature_flag_off_blocks_write(self):
        self.fake_frappe.conf.clear()
        with self.assertRaises(PermissionError):
            self.api.request_assessment("LIBRE", "", "Entreprise",
                                        "Demande assistance", True, "r-12345")

    def test_customer_must_be_bound_to_one_customer(self):
        self.fake_policy.customer = lambda: (_ for _ in ()).throw(PermissionError("no customer"))
        with self.assertRaises(PermissionError):
            self.api.request_assessment("LIBRE", "", "Entreprise",
                                        "Demande assistance", True, "r-12345")

    def test_admin_queue_rejects_customer(self):
        with self.assertRaises(PermissionError):
            self.api.get_admin_queue()

    def test_catalog_readable_without_write_privileges(self):
        self.fake_frappe.session.user = "Guest"
        catalog = self.api.get_catalog()
        self.assertEqual(len(catalog["tiers"]), 3)
        with self.assertRaises(PermissionError):
            self.api.get_admin_queue()

    def test_readiness_reports_structure_banks_and_email_flag_without_credentials(self):
        doctypes = {"SS97 Technician Exam Question", "SS97 Technician Exam Attempt",
                    "SS97 Technician Profile", "SS97 Technician Mission",
                    "SS97 Technician OS Event", "SS97 Technician Document",
                    "SS97 Technician Notice", "SS97 Technician Settlement"}
        def fake_bank_rows(_doctype, filters, **_kwargs):
            total = {"L2": 20, "BANK": 30, "CYBER": 40}[filters["track"]]
            return [{"prompt": f"Question de vérification {filters['track']} numéro {i + 1}",
                     "options_json": json.dumps({"A": "Réponse A", "B": "Réponse B",
                                                  "C": "Réponse C", "D": "Réponse D"}),
                     "correct_option": "A", "category": "Général"}
                    for i in range(total)]
        self.fake_frappe.get_all = fake_bank_rows
        self.fake_frappe.db = types.SimpleNamespace(
            get_value=lambda table, user, field: 1,
            exists=lambda table, name: name in doctypes,
            count=lambda table, filters: {"L2": 20, "BANK": 30, "CYBER": 40}[filters["track"]],
        )
        self.fake_frappe.get_roles = lambda user: ["System Manager"]
        self.fake_frappe.conf["ss97_tech_email_notifications"] = {"enabled": False}
        result = self.api.get_admin_readiness()
        self.assertTrue(result["technician_schema_ready"])
        self.assertTrue(result["exam_schema_ready"])
        self.assertFalse(result["technician_email_enabled"])
        self.assertEqual((result["n2_question_count"], result["n3_question_count"],
                          result["n4_question_count"]), (20, 30, 40))
        self.assertTrue(result["question_banks_ready"])
        self.assertFalse(result["stripe_connect_transfers_enabled"])

    def test_disabled_manager_account_cannot_read_readiness(self):
        self.fake_frappe.db = types.SimpleNamespace(get_value=lambda *args: 0)
        self.fake_frappe.get_roles = lambda user: ["System Manager"]
        with self.assertRaises(PermissionError):
            self.api.get_admin_readiness()

    def test_unavailable_private_bank_is_not_reported_ready_or_disclosed(self):
        doctypes = {"SS97 Technician Exam Question", "SS97 Technician Exam Attempt"}
        self.fake_frappe.db = types.SimpleNamespace(
            get_value=lambda *args: 1,
            exists=lambda table, name: name in doctypes,
            count=lambda table, filters: 40,
        )
        self.fake_frappe.get_roles = lambda user: ["System Manager"]
        self.fake_frappe.get_all = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("PRIVATE_ANSWER_MUST_NOT_LEAK"))
        result = self.api.get_admin_readiness()
        self.assertFalse(result["question_banks_ready"])
        self.assertTrue(result["question_bank_audit"]["CYBER"]["unavailable"])
        self.assertNotIn("PRIVATE_ANSWER_MUST_NOT_LEAK", str(result))


if __name__ == "__main__":
    unittest.main()
