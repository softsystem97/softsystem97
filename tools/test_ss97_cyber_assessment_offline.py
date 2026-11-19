"""Cyber intake unit contracts. No remote scan, mail, client or production write."""

import importlib
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from softsystem97.cyber_assessment.catalog import (TIERS, QUESTIONS, build_ticket,
    request_payload, validate_profile, validate_answers, self_assessment)
from softsystem97.cyber_assessment.pricing import euro, snapshot
from softsystem97.cyber_assessment.report import report_html

PROFILE = {"sector": "Commerce", "country": "France", "city": "Fort-de-France",
           "employees": "1-10", "sites": 1, "devices": 5,
           "contact_role": "Direction", "data_type": "PERSONAL"}
ANSWERS = {key: "UNKNOWN" for key in QUESTIONS}


class CyberCatalogTests(unittest.TestCase):
    def test_frappe_price_settings_uses_standard_single_doctype_metadata(self):
        path = (Path(__file__).resolve().parents[1] / "softsystem97" /
                "softsystem97/doctype/ss97_cyber_pricing/ss97_cyber_pricing.json")
        doctype = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(doctype["issingle"], 1)
        self.assertNotIn("is_single", doctype)

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
        self.assertIn("Ultra", detail)
        self.assertIn("Aucun test d'intrusion", detail)
        self.assertNotIn("password", detail)

    def test_free_ticket_uses_distinct_marker(self):
        payload = request_payload("LIBRE", "", "École", "PC ralenti", True)
        subject, detail = build_ticket(payload)
        self.assertTrue(subject.startswith("[SS97-LIBRE]"))
        self.assertIn("Ticket libre", detail)

    def test_n2_n3_are_distinct_without_cyber_tier(self):
        for kind in ("GENERALISTE", "BANQUE"):
            with self.subTest(kind=kind):
                result = request_payload(kind, "", "Entreprise", "Aide technique", True)
                subject, _ = build_ticket(result)
                self.assertIn(kind, subject)

    def test_complete_self_assessment_and_input_rejection(self):
        self.assertEqual(len(QUESTIONS), 10)
        self.assertEqual(validate_profile(PROFILE)["sites"], 1)
        self.assertEqual(validate_answers(ANSWERS), ANSWERS)
        result = self_assessment(ANSWERS)
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["unknown_count"], 10)
        self.assertEqual(self_assessment({key: "YES" for key in QUESTIONS})["score"], 100)
        for bad in ({**PROFILE, "devices": -5}, {**PROFILE, "cities": "autre"},
                    {**PROFILE, "sites": True}, {**PROFILE, "data_type": "PASSWORDS"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_profile(bad)
        with self.assertRaises(ValueError):
            validate_answers({**ANSWERS, "mfa": "arbitrary"})

    def test_prices_fail_closed_and_are_precise(self):
        self.assertEqual(euro("120.50"), "120.50")
        for bad in ("0", "-1", "19.999", "NaN", "Infinity", "100001", 2.1, None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                euro(bad)
        self.assertIsNone(snapshot({"is_published": 0, "basique_eur": "50.00",
                                   "premium_eur": "100.00", "ultra_eur": "200.00"}))
        self.assertEqual(snapshot({"is_published": 1, "basique_eur": "50.00",
                                   "premium_eur": "100.00", "ultra_eur": "200.00"})["EXTREME"],
                         "200.00")

    def test_report_html_escapes_untrusted_fields_and_disclaims_scope(self):
        doc = types.SimpleNamespace(name="dossier", ticket="ISS-001",
                                    organization="<script>alert('x')</script>",
                                    tier="SUPERIEUR", price_eur="100.00", state="RECEIVED")
        html = report_html(doc, PROFILE, ANSWERS)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("NON validé", html)
        self.assertIn("aucun", html.lower())


class CyberApiTests(unittest.TestCase):
    def setUp(self):
        self.fake_frappe = types.ModuleType("frappe")
        self.fake_frappe.__path__ = []
        self.fake_frappe.PermissionError = PermissionError
        self.fake_frappe.whitelist = lambda **kwargs: (lambda fn: fn)
        self.fake_frappe.conf = {"ss97_cyber_assessment": {"enabled": True}}
        self.fake_frappe.session = types.SimpleNamespace(user="client@example.test")
        self.fake_frappe.db = types.SimpleNamespace(
            get_value=lambda *args, **kwargs: 1,
            exists=lambda *args: False)
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
        result = self.api.request_assessment("GENERALISTE", "", "Entreprise",
                                             "Revue des habilitations", True, "r-12345")
        self.assertEqual(result["name"], "ISS-TEST-001")
        self.assertEqual(result["tier"], "")

    def test_cyber_intake_requires_published_prices_before_issue(self):
        with self.assertRaises(PermissionError):
            self.api.request_assessment("CYBER", "SUPERIEUR", "Entreprise",
                "Revue des habilitations", True, "r-12345", PROFILE, ANSWERS)

    def test_cyber_intake_creates_dossier_after_scoped_ticket(self):
        class FakeDoc:
            name = "a" * 36
            def insert(self, **kwargs):
                return self
        created = []
        def get_doc(payload, *args, **kwargs):
            if isinstance(payload, dict):
                created.append(payload)
                return FakeDoc()
            raise AssertionError("unexpected read")
        self.fake_frappe.get_doc = get_doc
        self.fake_frappe.db = types.SimpleNamespace(
            get_value=lambda doctype, name, field: None,
            exists=lambda doctype, name: True)
        with patch.object(self.api, "_prices", return_value={"SUPERIEUR": "100.00"}):
            result = self.api.request_assessment("CYBER", "SUPERIEUR", "Entreprise",
                "Revue des habilitations", True, "r-12345", PROFILE, ANSWERS)
        self.assertEqual(result["assessment_id"], "a" * 36)
        self.assertEqual(result["estimate_eur"], "100.00")
        self.assertEqual(created[0]["customer"], "CLIENT-1")
        self.assertEqual(created[0]["state"], "RECEIVED")
        self.assertEqual(json.loads(created[0]["answers_json"]), ANSWERS)

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
        self.assertEqual(len(catalog["questions"]), 10)
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

    def test_customer_cannot_set_pricing_or_link_order(self):
        with self.assertRaises(PermissionError):
            self.api.set_admin_pricing("10.00", "20.00", "30.00", True)
        with self.assertRaises(PermissionError):
            self.api.link_commercial_document("a" * 36, "Sales Invoice", "INV-1")

    def test_wrong_customer_financial_document_is_rejected_even_for_manager(self):
        self.fake_frappe.get_roles = lambda user: ["System Manager"]
        self.fake_frappe.db = types.SimpleNamespace(
            get_value=lambda *args: 1, exists=lambda *args: True)
        dossier = types.SimpleNamespace(name="a" * 36, customer="CUSTOMER-OUR")
        commercial = types.SimpleNamespace(name="INV-OTHER", customer="CUSTOMER-OTHER",
                                           docstatus=1, check_permission=lambda *_: None)
        saved = []
        dossier.set = lambda *args: saved.append(args)
        dossier.save = lambda *args, **kwargs: saved.append("SAVE")
        self.fake_frappe.get_doc = lambda doctype, *args, **kwargs: commercial
        with patch.object(self.api, "_dossier", return_value=dossier):
            with self.assertRaises(PermissionError):
                self.api.link_commercial_document("a" * 36, "Sales Invoice", "INV-OTHER")
        self.assertEqual(saved, [])

    def test_n2_and_n3_cannot_review_n4_dossier(self):
        dossier = types.SimpleNamespace(name="a" * 36, state="RECEIVED")
        with patch.object(self.api, "_dossier", return_value=dossier), patch.object(
            self.api, "_n4_authorized", side_effect=PermissionError("N4 required")):
            with self.assertRaises(PermissionError):
                self.api.review_assessment("a" * 36, "APPROVED_N4",
                    "Le rapport a été lu et les contrôles sont cohérents.", "MANDAT-1")
        self.assertEqual(dossier.state, "RECEIVED")

    def test_n4_approval_requires_a_long_note_and_evidence(self):
        dossier = types.SimpleNamespace(name="a" * 36, state="RECEIVED")
        with patch.object(self.api, "_dossier", return_value=dossier), patch.object(
            self.api, "_n4_authorized", return_value=True):
            with self.assertRaises(ValueError):
                self.api.review_assessment("a" * 36, "APPROVED_N4", "Bon", "MANDAT-1")
            with self.assertRaises(ValueError):
                self.api.review_assessment("a" * 36, "APPROVED_N4",
                    "Analyse des preuves documentées avec révision contrôlée.", "")
        self.assertEqual(dossier.state, "RECEIVED")

    def test_other_customers_cannot_download_private_report(self):
        dossier = types.SimpleNamespace(name="a" * 36)
        with patch.object(self.api, "_dossier", return_value=dossier), patch.object(
            self.api, "_visible", side_effect=PermissionError("customer mismatch")):
            with self.assertRaises(PermissionError):
                self.api.download_report("a" * 36)

    def test_authorized_pdf_is_private_download_without_public_file(self):
        dossier = types.SimpleNamespace(name="a" * 36, ticket="ISS-001",
            organization="Entreprise", tier="ESSENTIEL", price_eur="99.00",
            state="RECEIVED", profile_json=json.dumps(PROFILE),
            answers_json=json.dumps(ANSWERS))
        fake_pdf = types.ModuleType("frappe.utils.pdf")
        captured = []
        fake_pdf.get_pdf = lambda html, options: (captured.append(html) or b"%PDF-example")
        self.fake_frappe.local = types.SimpleNamespace(response=types.SimpleNamespace())
        with patch.object(self.api, "_dossier", return_value=dossier), patch.object(
            self.api, "_visible", return_value="customer"), patch.dict(sys.modules,
            {"frappe.utils.pdf": fake_pdf}):
            self.api.download_report("a" * 36)
        self.assertEqual(self.fake_frappe.local.response.type, "download")
        self.assertEqual(self.fake_frappe.local.response.filecontent, b"%PDF-example")
        self.assertIn("Pré-diagnostic", captured[0])


if __name__ == "__main__":
    unittest.main()
