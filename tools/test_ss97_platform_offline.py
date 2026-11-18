"""Offline tests for SS97 V2–V10. No real Frappe site or MeshCentral is used."""

import importlib
import json
import sys
import types
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from softsystem97.platform.registry import (
    ALLOWED_STATES, MODULES, can_change_state, catalog, overlaps,
    schedule_window, validate_payload,
)


SAMPLES = {
    "V2": {"title": "Intervention imprimante", "starts_at": "2026-11-18T15:00:00Z", "minutes": 60},
    "V3": {"symptoms": "Impossible d'imprimer", "risk": "medium"},
    "V4": {"coordination_note": "Le client attend la résolution du ticket."},
    "V5": {"category": "network", "urgency": "high", "description": "Plus de connexion."},
    "V6": {"asset_name": "Dell laboratoire", "asset_type": "laptop", "inventory_authorized": True},
    "V7": {"asset_record": str(uuid4()), "interval_days": 60, "next_due": "2027-01-18"},
    "V8": {"specialty": "networks", "escalation_reason": "Besoin d'un expert réseau."},
    "V9": {"finding": "Mises à jour non appliquées", "severity": "high"},
    "V10": {"partner_name": "Partenaire candidat", "offering": "Maintenance spécialisée"},
}


class RegistryTests(unittest.TestCase):
    def test_nineteen_versions_are_real_schemas(self):
        self.assertEqual(list(MODULES), ["V" + str(i) for i in range(2, 21)])
        self.assertEqual(len(catalog()), 19)
        self.assertEqual(len(catalog(["V" + str(i) for i in range(2, 11)])), 9)

    def test_every_module_accepts_a_valid_record(self):
        for version, payload in SAMPLES.items():
            with self.subTest(version=version):
                self.assertEqual(validate_payload(version, payload), payload)

    def test_unexpected_and_missing_fields_rejected(self):
        for version, payload in SAMPLES.items():
            with self.subTest(version=version):
                with self.assertRaises(ValueError):
                    validate_payload(version, {**payload, "customer": "OTHER"})
                with self.assertRaises(ValueError):
                    validate_payload(version, {})

    def test_inventory_needs_explicit_true(self):
        with self.assertRaisesRegex(ValueError, "Autorisation"):
            validate_payload("V6", {**SAMPLES["V6"], "inventory_authorized": False})

    def test_bad_duration_or_bool_number_rejected(self):
        for minutes in (0, 181, True, "60", -1):
            with self.subTest(minutes=minutes), self.assertRaises(ValueError):
                validate_payload("V2", {**SAMPLES["V2"], "minutes": minutes})

    def test_dates_and_uuid_are_strict(self):
        for bad in ("2026-02-30", "yesterday", "2027-1-4"):
            with self.assertRaises(ValueError):
                validate_payload("V7", {**SAMPLES["V7"], "next_due": bad})
        with self.assertRaises(ValueError):
            validate_payload("V7", {**SAMPLES["V7"], "asset_record": "../../other"})

    def test_diagnostics_require_enumerated_risk(self):
        with self.assertRaises(ValueError):
            validate_payload("V9", {**SAMPLES["V9"], "severity": "SUPERADMIN"})

    def test_schedule_overlap_and_adjoining_slots(self):
        start, end = schedule_window(SAMPLES["V2"])
        self.assertTrue(overlaps(start, end, start + timedelta(minutes=30), end))
        self.assertFalse(overlaps(start, end, end, end + timedelta(minutes=30)))

    def test_customer_can_only_cancel_own_sos(self):
        self.assertTrue(can_change_state("SUBMITTED", "CANCELLED", "client", "V5"))
        self.assertFalse(can_change_state("SUBMITTED", "IN_REVIEW", "client", "V5"))
        self.assertFalse(can_change_state("SUBMITTED", "CANCELLED", "client", "V9"))
        self.assertTrue(can_change_state("SUBMITTED", "IN_REVIEW", "technician", "V9"))
        self.assertFalse(can_change_state("COMPLETED", "IN_REVIEW", "technician", "V9"))

    def test_schema_files_are_valid_and_restricted(self):
        root = Path(__file__).resolve().parents[1]
        for slug in ("ss97_platform_record", "ss97_platform_event"):
            path = root / "softsystem97/softsystem97/doctype" / slug / (slug + ".json")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["permissions"], [{"role": "System Manager", "read": 1, "report": 1}])
            self.assertEqual(data["allow_rename"], 0)


class Denied(Exception):
    pass


def _api():
    frappe = types.ModuleType("frappe")
    frappe.PermissionError = Denied
    frappe.whitelist = lambda **kwargs: lambda func: func
    frappe.throw = lambda message, *args: (_ for _ in ()).throw(Denied(message))
    frappe.conf = {"ss97_v1_v10": {"enabled": True}}
    frappe.db = SimpleNamespace(table_exists=lambda name: True)
    frappe.session = SimpleNamespace(user="test@ss97.invalid")
    utils = types.ModuleType("frappe.utils")
    utils.now_datetime = lambda: __import__("datetime").datetime(2026, 11, 18)
    integrations = types.ModuleType("softsystem97.integrations")
    integrations.__path__ = []
    bridge = types.ModuleType("softsystem97.integrations.ticket_bridge")
    bridge.__path__ = []
    policy = types.ModuleType("softsystem97.integrations.ticket_bridge.policy")
    policy.settings = lambda: None
    policy.active_user = lambda: "test@ss97.invalid"
    policy.authorize = lambda ticket, audience: "test@ss97.invalid"
    bridge.policy = policy
    with patch.dict(sys.modules, {"frappe": frappe, "frappe.utils": utils,
        "softsystem97.integrations": integrations,
        "softsystem97.integrations.ticket_bridge": bridge,
        "softsystem97.integrations.ticket_bridge.policy": policy}):
        import softsystem97.platform.api as imported
        return importlib.reload(imported), frappe


class ApiSafetyTests(unittest.TestCase):
    def setUp(self):
        self.api, self.frappe = _api()
        self.ticket = SimpleNamespace(name="ISS-TEST", status="Open", customer="CUSTOMER_A", raised_by="client@a.invalid")

    def test_unconfigured_site_fails_closed(self):
        self.frappe.conf["ss97_v1_v10"] = {}
        with self.assertRaises(Denied):
            self.api.get_catalog()

    def test_unknown_client_cannot_read_other_ticket(self):
        self.frappe.db.exists = lambda dt, key: True
        self.frappe.get_doc = lambda *args: self.ticket
        with patch.object(self.api.policy, "authorize", side_effect=Denied("other tenant")):
            with self.assertRaises(Denied):
                self.api._ticket(self.ticket.name, "client")

    def test_client_cannot_create_internal_versions(self):
        with patch.object(self.api, "_enabled"):
            with self.assertRaises(Denied):
                self.api.create_record("V9", "ISS-TEST", json.dumps(SAMPLES["V9"]), "client")

    def test_asset_link_rejects_other_tenant_or_ticket(self):
        for bad in ({"version": "V6", "ticket_name": "ISS-OTHER", "customer": "CUSTOMER_A", "state": "SUBMITTED"},
                    {"version": "V6", "ticket_name": "ISS-TEST", "customer": "CUSTOMER_B", "state": "SUBMITTED"},
                    {"version": "V5", "ticket_name": "ISS-TEST", "customer": "CUSTOMER_A", "state": "SUBMITTED"}):
            self.frappe.db.get_value = lambda *args, **kwargs: SimpleNamespace(**bad)
            with self.subTest(bad=bad), self.assertRaises(Denied):
                self.api._validate_asset_link("V7", SAMPLES["V7"], self.ticket)

    def test_ticket_link_cannot_be_supplied_by_payload(self):
        with patch.object(self.api, "_enabled"), patch.object(self.api, "_ticket", return_value=(self.ticket, "tech@ss97.invalid")):
            with self.assertRaises(Denied):
                self.api.create_record("V5", "ISS-TEST", json.dumps({**SAMPLES["V5"], "customer": "OTHER"}))

    def test_public_v1_is_not_duplicate_action(self):
        self.assertNotIn("V1", MODULES)

    def test_create_record_uses_server_ticket_and_actor(self):
        created = []

        def make_doc(values):
            created.append(values)
            doc = SimpleNamespace(**values, name=values["record_id"], creation="2026-11-18")
            doc.insert = lambda **kwargs: doc
            return doc

        self.frappe.get_doc = make_doc
        with patch.object(self.api, "_enabled"), patch.object(self.api, "_ticket", return_value=(self.ticket, "tech@ss97.invalid")), patch.object(self.api, "_log"):
            result = self.api.create_record("V3", self.ticket.name, json.dumps(SAMPLES["V3"]))
        self.assertEqual(created[0]["customer"], "CUSTOMER_A")
        self.assertEqual(created[0]["ticket_name"], self.ticket.name)
        self.assertEqual(created[0]["technician"], "tech@ss97.invalid")
        self.assertEqual(created[0]["state"], "SUBMITTED")
        self.assertEqual(result["version"], "V3")

    def test_closed_ticket_cannot_create_records(self):
        self.ticket.status = "Closed"
        with patch.object(self.api, "_enabled"), patch.object(self.api, "_ticket", return_value=(self.ticket, "tech@ss97.invalid")):
            with self.assertRaises(Denied):
                self.api.create_record("V3", self.ticket.name, json.dumps(SAMPLES["V3"]))

    def test_overlapping_missions_blocked_in_transaction(self):
        self.frappe.db.sql = lambda *args, **kwargs: [("tech@ss97.invalid",)]
        self.frappe.get_all = lambda *args, **kwargs: [SimpleNamespace(
            starts_at="2026-11-18T15:30:00Z", ends_at="2026-11-18T16:30:00Z")]
        start, end = schedule_window(SAMPLES["V2"])
        with self.assertRaisesRegex(Denied, "déjà une mission"):
            self.api._reserve_schedule("tech@ss97.invalid", start, end)

    def test_get_record_checks_customer_identity(self):
        record = SimpleNamespace(ticket_name=self.ticket.name, customer="OTHER", version="V9")
        with patch.object(self.api, "_enabled"), patch.object(self.api, "_record", return_value=record), patch.object(
                self.api, "_ticket", return_value=(self.ticket, "client@a.invalid")):
            with self.assertRaises(Denied):
                self.api.get_record(str(uuid4()), "client")

    def test_client_can_cancel_own_sos_but_cannot_complete(self):
        record = SimpleNamespace(ticket_name=self.ticket.name, customer=self.ticket.customer,
            state="SUBMITTED", version="V5", save=lambda **kwargs: None)
        with patch.object(self.api, "_enabled"), patch.object(self.api, "_record", return_value=record), patch.object(
                self.api, "_ticket", return_value=(self.ticket, "client@a.invalid")), patch.object(
                self.api, "_log"), patch.object(self.api, "_view", return_value={"state": "CANCELLED"}):
            with self.assertRaises(Denied):
                self.api.set_record_state(str(uuid4()), "COMPLETED", "client")
            self.assertEqual(self.api.set_record_state(str(uuid4()), "CANCELLED", "client")["state"], "CANCELLED")
            self.assertEqual(record.state, "CANCELLED")

    def test_cross_company_record_cannot_be_completed(self):
        record = SimpleNamespace(ticket_name=self.ticket.name, customer="OTHER", state="IN_REVIEW", version="V9")
        with patch.object(self.api, "_enabled"), patch.object(self.api, "_record", return_value=record), patch.object(
                self.api, "_ticket", return_value=(self.ticket, "tech@ss97.invalid")):
            with self.assertRaises(Denied):
                self.api.set_record_state(str(uuid4()), "COMPLETED")

    def test_v4_overview_only_uses_ticket_scoped_data(self):
        self.frappe.db.table_exists = lambda dt: True
        calls = []

        def query(doctype, **kwargs):
            calls.append((doctype, kwargs["filters"]))
            return [SimpleNamespace(name="s1", state="CLIENT_APPROVED",
                                    technician="tech@ss97.invalid", expires_at="2026-11-18")]

        self.frappe.get_all = query
        with patch.object(self.api, "_enabled"), patch.object(self.api, "_ticket", return_value=(self.ticket, "tech@ss97.invalid")), patch.object(
                self.api, "list_records", return_value={"records": []}):
            response = self.api.get_case_overview(self.ticket.name, "technician")
        self.assertEqual(response["remote_sessions"][0]["state"], "CLIENT_APPROVED")
        self.assertEqual(calls[0][1]["customer"], "CUSTOMER_A")
        self.assertEqual(calls[0][1]["client_user"], "client@a.invalid")
        self.assertEqual(calls[0][1]["technician"], "tech@ss97.invalid")


if __name__ == "__main__":
    unittest.main()
