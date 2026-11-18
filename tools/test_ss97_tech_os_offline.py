"""Offline contract/security regression tests; no Frappe site, Stripe or client accessed."""

import ast
import importlib
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from softsystem97.technician_os.rules import (
    MISSION_TRANSITIONS, PROFILE_TRANSITIONS, TRACKS, exact_track_role,
    fee_eur, next_mission_state, next_profile_state, reference, short_note,
    track_settings,
)


ROOT = Path(__file__).resolve().parents[1]


class TechnicianOSRulesTests(unittest.TestCase):
    def test_exact_three_specialties(self):
        self.assertEqual(set(TRACKS), {"L2", "BANK", "CYBER"})
        self.assertEqual(len({item["role"] for item in TRACKS.values()}), 3)

    def test_must_have_one_and_only_one_track_role(self):
        self.assertTrue(exact_track_role(["SS97 Technicien N2", "Customer"], "L2"))
        for roles in ([], ["Candidat SS97"], ["SS97 Technicien N3"],
                      ["SS97 Technicien N2", "SS97 Technicien N4"]):
            with self.subTest(roles=roles):
                self.assertFalse(exact_track_role(roles, "L2"))

    def test_unknown_track_fails_closed(self):
        for bad in ("N4", "ALL", "", None):
            with self.subTest(track=bad), self.assertRaises(ValueError):
                track_settings(bad)

    def test_profile_no_skip_to_active(self):
        self.assertFalse(next_profile_state("APPLIED", "ACTIVE"))
        self.assertFalse(next_profile_state("IN_REVIEW", "CONTRACT_SIGNED"))
        self.assertTrue(next_profile_state("CONTRACT_SIGNED", "ACTIVE"))
        self.assertTrue(next_profile_state("ACTIVE", "SUSPENDED"))
        self.assertFalse(next_profile_state("REJECTED", "ACTIVE"))
        self.assertEqual(set(PROFILE_TRANSITIONS["REJECTED"]), set())

    def test_mission_requires_risk_approval_and_report(self):
        self.assertFalse(next_mission_state("PENDING_APPROVAL", "ACCEPTED"))
        self.assertTrue(next_mission_state("PENDING_APPROVAL", "OFFERED"))
        self.assertFalse(next_mission_state("OFFERED", "CLIENT_ACCEPTED"))
        self.assertFalse(next_mission_state("IN_PROGRESS", "CLIENT_ACCEPTED"))
        self.assertTrue(next_mission_state("REPORT_SUBMITTED", "CLIENT_ACCEPTED"))
        self.assertFalse(next_mission_state("CLIENT_ACCEPTED", "IN_PROGRESS"))
        self.assertFalse(next_mission_state("DISPUTED", "IN_PROGRESS"))
        self.assertFalse(next_mission_state("REWORK_PENDING_APPROVAL", "IN_PROGRESS"))
        self.assertTrue(next_mission_state("DISPUTED", "CANCELLED"))

    def test_fee_is_positive_rounded_eur_string_not_float(self):
        self.assertEqual(fee_eur("12"), "12.00")
        self.assertEqual(fee_eur("12.50"), "12.50")
        for bad in (0, 1.5, -2, "0", "-1", "1.234", "1e3", "100001", "NaN", "", None):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                fee_eur(bad)

    def test_external_references_are_human_verified(self):
        self.assertEqual(reference(" REFERENCE-12345 "), "REFERENCE-12345")
        for bad in ("", "123", "\nref99999", "a" * 121):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                reference(bad)

    def test_report_text_length(self):
        self.assertEqual(short_note(" intervention "), "intervention")
        for bad in ("", 4, "x" * 2001):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                short_note(bad)

    def test_only_admin_can_read_private_doctypes_directly(self):
        names = ("ss97_technician_profile", "ss97_technician_mission",
                 "ss97_technician_os_event")
        for name in names:
            path = (ROOT / "softsystem97" / "softsystem97" / "doctype" / name / f"{name}.json")
            with self.subTest(doctype=name):
                doc = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(doc["permissions"], [{"role": "System Manager", "read": 1, "report": 1}])
                self.assertFalse(any(field.get("fieldname") in {"rib", "iban", "bank_account", "password"}
                                     for field in doc["fields"]))

    def test_server_api_no_guest_writes_or_money_transfer(self):
        api = (ROOT / "softsystem97" / "technician_os" / "api.py").read_text(encoding="utf-8")
        tree = ast.parse(api)
        self.assertNotIn("allow_guest=True", api)
        self.assertNotIn("stripe.Transfer.create", api)
        self.assertNotIn("payouts.create", api)
        self.assertNotIn("frappe.sendmail", api)
        names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        self.assertTrue({"apply", "review_profile", "offer_mission", "approve_sensitive_mission",
                         "transition_my_mission", "review_client_report", "get_my_workspace",
                         "get_admin_overview", "cancel_mission"} <= names)

    def test_separate_pages_have_hard_server_guards(self):
        page_targets = {"ss97-tech-n2": "L2", "ss97-tech-banque": "BANK",
                        "ss97-tech-cyber": "CYBER"}
        for slug, track in page_targets.items():
            source = (ROOT / "softsystem97" / "www" / f"{slug}.py").read_text(encoding="utf-8")
            with self.subTest(slug=slug):
                self.assertIn(f'technician_page(context, "{track}")', source)
                html = (ROOT / "softsystem97" / "www" / f"{slug}.html").read_text(encoding="utf-8")
                self.assertIn(f'data-track="{track}"', html)
        guard = (ROOT / "softsystem97" / "technician_os" / "pages.py").read_text(encoding="utf-8")
        self.assertIn("_my_active_profile()", guard)
        self.assertIn("profile.track != track", guard)
        self.assertIn("_manager()", guard)

    def test_admin_api_excludes_bank_identifiers(self):
        source = (ROOT / "softsystem97" / "technician_os" / "api.py").read_text(encoding="utf-8")
        self.assertIn('def get_admin_overview():', source)
        self.assertIn('"candidate_user", "track", "state"', source)
        self.assertNotIn('"iban"', source)
        self.assertNotIn('"rib"', source)

    def test_wrong_universe_is_rejected_before_html_context(self):
        fake_frappe = types.ModuleType("frappe")
        fake_frappe.__path__ = []
        fake_frappe.PermissionError = PermissionError
        fake_frappe.throw = lambda message, kind=PermissionError: (_ for _ in ()).throw(kind(message))
        fake_frappe.whitelist = lambda **_kw: lambda func: func
        fake_utils = types.ModuleType("frappe.utils")
        fake_utils.now_datetime = lambda: None
        fake_frappe.utils = fake_utils
        with patch.dict(sys.modules, {"frappe": fake_frappe, "frappe.utils": fake_utils}):
            page_module = importlib.import_module("softsystem97.technician_os.pages")
            try:
                page_module._enabled = lambda: None
                page_module._my_active_profile = lambda: types.SimpleNamespace(track="L2")
                with self.assertRaises(PermissionError):
                    page_module.technician_page(types.SimpleNamespace(), "CYBER")
                with self.assertRaises(PermissionError):
                    page_module.technician_page(types.SimpleNamespace(), "BANK")
                context = types.SimpleNamespace()
                page_module.technician_page(context, "L2")
                self.assertEqual(context.tech_track, "L2")
                self.assertEqual(context.no_cache, 1)
            finally:
                sys.modules.pop("softsystem97.technician_os.pages", None)
                sys.modules.pop("softsystem97.technician_os.api", None)

    def test_client_view_never_exposes_technician_pay_or_private_authorization(self):
        fake_frappe = types.ModuleType("frappe")
        fake_frappe.__path__ = []
        fake_frappe.whitelist = lambda **_kw: lambda func: func
        fake_utils = types.ModuleType("frappe.utils")
        fake_utils.now_datetime = lambda: None
        fake_frappe.utils = fake_utils
        with patch.dict(sys.modules, {"frappe": fake_frappe, "frappe.utils": fake_utils}):
            module = importlib.import_module("softsystem97.technician_os.api")
            try:
                mission = types.SimpleNamespace(
                    name="mission-1", ticket_name="ISS-001", track="CYBER",
                    state="REPORT_SUBMITTED", offered_fee_eur="900.00",
                    route_instructions="Confidentiel", report_summary="Intervention terminée",
                    authorization_reference="AUTH-CYBER-PRIVATE",
                )
                customer = module._mission_view(mission, as_client=True)
                technician = module._mission_view(mission, as_client=False)
                self.assertNotIn("offered_fee_eur", customer)
                self.assertNotIn("route_instructions", customer)
                self.assertNotIn("authorization_reference", customer)
                self.assertEqual(technician["offered_fee_eur"], "900.00")
            finally:
                sys.modules.pop("softsystem97.technician_os.api", None)

    def test_client_report_decision_requires_ticket_authorization(self):
        fake_frappe = types.ModuleType("frappe")
        fake_frappe.__path__ = []
        fake_frappe.PermissionError = PermissionError
        fake_frappe.whitelist = lambda **_kwargs: lambda fn: fn
        fake_frappe.get_roles = lambda user: ["Customer"]
        fake_frappe.throw = lambda msg, kind=PermissionError: (_ for _ in ()).throw(kind(msg))
        fake_utils = types.ModuleType("frappe.utils")
        fake_utils.now_datetime = lambda: "2026-11-18 12:00:00"
        fake_frappe.utils = fake_utils
        with patch.dict(sys.modules, {"frappe": fake_frappe, "frappe.utils": fake_utils}):
            module = importlib.import_module("softsystem97.technician_os.api")
            try:
                mission = types.SimpleNamespace(
                    name="m" * 36, ticket_name="ISS-001",
                    technician="worker@example.test", track="CYBER",
                    state="REPORT_SUBMITTED", report_summary="Intervention contrôlée",
                    client_accepted_at=None, save=lambda **kwargs: None,
                )
                module._enabled = lambda: None
                module._user = lambda: "client@example.test"
                module._mission_by_id = lambda *args, **kwargs: mission
                module._log = lambda *args: None
                module._authorized_ticket = lambda *args: (_ for _ in ()).throw(
                    PermissionError("Autre client"))
                with self.assertRaises(PermissionError):
                    module.review_client_report(mission.name, "CLIENT_ACCEPTED")
                self.assertEqual(mission.state, "REPORT_SUBMITTED")
                module._authorized_ticket = lambda *args: types.SimpleNamespace(status="Open")
                result = module.review_client_report(mission.name, "CLIENT_ACCEPTED")
                self.assertEqual(mission.state, "CLIENT_ACCEPTED")
                self.assertNotIn("offered_fee_eur", result)
                self.assertNotIn("payment_status", result)
                self.assertEqual(mission.client_accepted_at, "2026-11-18 12:00:00")
                mission.state = "REPORT_SUBMITTED"
                with self.assertRaises(PermissionError):
                    module.review_client_report(mission.name, "DISPUTED")
                self.assertEqual(mission.state, "REPORT_SUBMITTED")
                result = module.review_client_report(mission.name, "DISPUTED", "Travail non terminé")
                self.assertEqual(result["dispute_reason"], "Travail non terminé")
                self.assertNotIn("offered_fee_eur", result)
            finally:
                sys.modules.pop("softsystem97.technician_os.api", None)

    def test_sensitive_dispute_rework_demands_fresh_mandate_and_second_manager(self):
        fake_frappe = types.ModuleType("frappe")
        fake_frappe.__path__ = []
        fake_frappe.PermissionError = PermissionError
        fake_frappe.whitelist = lambda **_kwargs: lambda fn: fn
        fake_frappe.throw = lambda msg, kind=PermissionError: (_ for _ in ()).throw(kind(msg))
        fake_utils = types.ModuleType("frappe.utils")
        fake_utils.now_datetime = lambda: "2026-11-18 13:00:00"
        fake_frappe.utils = fake_utils
        with patch.dict(sys.modules, {"frappe": fake_frappe, "frappe.utils": fake_utils}):
            module = importlib.import_module("softsystem97.technician_os.api")
            try:
                mission = types.SimpleNamespace(
                    name="a" * 36, ticket_name="ISS-001", customer="CUST-1",
                    technician="worker@test.invalid", track="CYBER", state="DISPUTED",
                    dispute_reason="Résultat non conforme", rework_count=0,
                    offered_fee_eur="100.00", route_instructions="Aucun secret",
                    report_summary="Premier compte rendu", report_submitted_at="2026-11-18",
                    created_by_user="coord@test.invalid", approved_by="second@test.invalid",
                    save=lambda **kwargs: None,
                )
                module._enabled = lambda: None
                module._manager = lambda: "manager_a@test.invalid"
                module._mission_by_id = lambda *args, **kwargs: mission
                module._rework_ticket = lambda m: types.SimpleNamespace(raised_by="client@test.invalid")
                module._log = lambda *args: None
                with self.assertRaises(PermissionError):
                    module.request_dispute_rework(mission.name, "REWORK-DECISION")
                self.assertEqual(mission.state, "DISPUTED")
                requested = module.request_dispute_rework(
                    mission.name, "REWORK-DECISION", "NEW-MANDATE-1234")
                self.assertEqual(requested["state"], "REWORK_PENDING_APPROVAL")
                self.assertEqual(mission.rework_count, 0)
                with self.assertRaises(PermissionError):
                    module.approve_sensitive_rework(mission.name)
                module._manager = lambda: "manager_b@test.invalid"
                approved = module.approve_sensitive_rework(mission.name)
                self.assertEqual(approved["state"], "IN_PROGRESS")
                self.assertEqual(mission.rework_count, 1)
                self.assertEqual(mission.report_summary, "")
                self.assertEqual(mission.rework_approved_by, "manager_b@test.invalid")
            finally:
                sys.modules.pop("softsystem97.technician_os.api", None)


if __name__ == "__main__":
    unittest.main()
