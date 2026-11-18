"""V11–V20 contract/permission tests. Never contacts Frappe Cloud or an agent."""

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from softsystem97.platform.registry import (
    EXTENDED_VERSIONS, MODULES, catalog, validate_payload,
)
from tools.test_ss97_platform_offline import Denied, _api


EXTENDED_SAMPLES = {
    "V11": {"device_alias": "Dell laboratoire", "display_issue": "black_screen"},
    "V12": {"symptom_summary": "Le poste met du temps à démarrer.", "affected_component": "system"},
    "V13": {"procedure_name": "Vérifier le service", "planned_steps": "Lire l'état du service.",
            "rollback_plan": "Ne rien modifier.", "execution_risk": "low"},
    "V14": {"service_request": "remote_help", "customer_need": "Assistance imprimante."},
    "V15": {"required_skill": "networks", "dispatch_note": "À revoir par le responsable."},
    "V16": {"site_alias": "Boutique A", "health_signal": "degraded",
            "observed_at": "2026-11-18T18:00:00Z"},
    "V17": {"backup_scope": "Serveur A", "restore_test_status": "planned",
            "evidence_note": "Test non encore réalisé."},
    "V18": {"case_summary": "Analyse du ticket client.",
            "suggested_actions": "Vérifier la connectivité.", "human_review": "pending"},
    "V19": {"organization_type": "municipality", "service_need": "Support aux services.",
            "project_stage": "discovery"},
    "V20": {"metric_type": "resolution_time", "source_description": "Statuts des tickets."},
}


class ExtendedSchemaTests(unittest.TestCase):
    def test_modules_are_ten_distinct_schema_versions(self):
        self.assertEqual(EXTENDED_VERSIONS, {"V" + str(i) for i in range(11, 21)})
        self.assertTrue(EXTENDED_VERSIONS.issubset(MODULES))
        self.assertEqual([module["version"] for module in catalog(EXTENDED_VERSIONS)],
                         ["V" + str(i) for i in range(11, 21)])

    def test_each_module_has_a_valid_strict_payload(self):
        for version, payload in EXTENDED_SAMPLES.items():
            with self.subTest(version=version):
                self.assertEqual(validate_payload(version, payload), payload)
                with self.assertRaises(ValueError):
                    validate_payload(version, {})
                with self.assertRaises(ValueError):
                    validate_payload(version, {**payload, "customer": "OTHER_TENANT"})
                with self.assertRaises(ValueError):
                    validate_payload(version, {**payload, "execute_command": "whoami"})

    def test_enum_cannot_be_replaced_with_arbitrary_remote_action(self):
        for version, field in (("V11", "display_issue"), ("V13", "execution_risk"),
                               ("V17", "restore_test_status"), ("V18", "human_review")):
            with self.subTest(version=version), self.assertRaises(ValueError):
                validate_payload(version, {**EXTENDED_SAMPLES[version], field: "run_remote"})

    def test_v16_observation_uses_strict_utc(self):
        for invalid in ("yesterday", "2026-11-18 18:00", "2026-02-30T14:00:00Z"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_payload("V16", {**EXTENDED_SAMPLES["V16"], "observed_at": invalid})

    def test_v17_requires_evidence_note_even_for_declared_success(self):
        with self.assertRaises(ValueError):
            validate_payload("V17", {"backup_scope": "Server A", "restore_test_status": "passed"})

    def test_frappes_select_field_includes_all_19_versions(self):
        root = Path(__file__).resolve().parents[1]
        path = root / "softsystem97/softsystem97/doctype/ss97_platform_record/ss97_platform_record.json"
        fields = json.loads(path.read_text(encoding="utf-8"))["fields"]
        version_field = next(field for field in fields if field["fieldname"] == "version")
        self.assertEqual(version_field["options"].splitlines(), list(MODULES))


class ExtendedPermissionTests(unittest.TestCase):
    def setUp(self):
        self.api, self.frappe = _api()
        self.ticket = SimpleNamespace(name="ISS-TEST", status="Open", customer="CUSTOMER_A",
                                      raised_by="client@a.invalid")

    def test_old_flag_alone_does_not_expose_v11_to_v20(self):
        response = self.api.get_catalog()
        self.assertEqual([mod["version"] for mod in response["modules"]],
                         ["V" + str(i) for i in range(2, 11)])
        with self.assertRaisesRegex(Denied, "non activée"):
            self.api.create_record("V11", self.ticket.name, json.dumps(EXTENDED_SAMPLES["V11"]))

    def test_explicit_extension_flag_must_be_boolean_true(self):
        for invalid in ("true", 1, {"enabled": 1}, {"enabled": "true"}, {}):
            self.frappe.conf["ss97_v11_v20"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(Denied):
                self.api._require_version("V20")

    def test_explicit_flag_exposes_only_validated_modules(self):
        self.frappe.conf["ss97_v11_v20"] = {"enabled": True}
        self.assertEqual(len(self.api.get_catalog()["modules"]), 19)

    def test_guest_or_client_cannot_create_internal_modules(self):
        self.frappe.conf["ss97_v11_v20"] = {"enabled": True}
        for version in EXTENDED_SAMPLES:
            with self.subTest(version=version), self.assertRaises(Denied):
                self.api.create_record(version, self.ticket.name,
                                       json.dumps(EXTENDED_SAMPLES[version]), "client")

    def test_disabled_extension_records_cannot_be_fetched_or_changed(self):
        record = SimpleNamespace(version="V18", ticket_name=self.ticket.name,
                                 customer="CUSTOMER_A", state="IN_REVIEW")
        with patch.object(self.api, "_record", return_value=record):
            with self.assertRaises(Denied):
                self.api.get_record("a" * 36)
            with self.assertRaises(Denied):
                self.api.set_record_state("a" * 36, "COMPLETED")

    def test_ticket_list_filters_out_disabled_extended_records(self):
        captured = {}

        def collect(doctype, **kwargs):
            captured.update(kwargs)
            return []

        self.frappe.get_all = collect
        with patch.object(self.api, "_ticket", return_value=(self.ticket, "client@a.invalid")):
            self.assertEqual(self.api.list_records(self.ticket.name)["records"], [])
        self.assertEqual(captured["filters"]["version"],
                         ["in", ["V" + str(i) for i in range(2, 11)]])
        self.assertEqual(captured["filters"]["customer"], "CUSTOMER_A")

    def test_technician_can_create_enabled_v11_record_under_server_ticket(self):
        self.frappe.conf["ss97_v11_v20"] = {"enabled": True}
        created = []

        def make_doc(data):
            created.append(data)
            doc = SimpleNamespace(**data, name=data["record_id"], creation="2026-11-18")
            doc.insert = lambda **kwargs: doc
            return doc

        self.frappe.get_doc = make_doc
        with patch.object(self.api, "_ticket", return_value=(self.ticket, "tech@ss97.invalid")), \
                patch.object(self.api, "_log"):
            response = self.api.create_record("V11", self.ticket.name,
                                              json.dumps(EXTENDED_SAMPLES["V11"]))
        self.assertEqual(response["version"], "V11")
        self.assertEqual(created[0]["customer"], "CUSTOMER_A")
        self.assertEqual(created[0]["technician"], "tech@ss97.invalid")


if __name__ == "__main__":
    unittest.main()
