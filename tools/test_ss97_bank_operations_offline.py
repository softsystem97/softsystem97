"""N3 workflow and permission checks on a synthetic Frappe interface."""

import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

from softsystem97.technician_os.bank_operation_rules import (
    CHOICES, REFERENCE_FIELDS, continuity_times, parse_operation, validate_operation_update,
)


class AccessDenied(Exception):
    pass


def throw(message, *args):
    raise AccessDenied(message)


def values(**overrides):
    return {
        **dict.fromkeys(REFERENCE_FIELDS, ""),
        **{key: allowed[0] for key, allowed in CHOICES.items()},
        "agency_ref": "AGENCE-A",
        "asset_ref": "POSTE-01",
        **overrides,
    }


class BankOperationRulesTests(unittest.TestCase):
    def test_workaround_requires_reference(self):
        with self.assertRaises(ValueError):
            parse_operation(values(service_state="WORKAROUND"))
        self.assertEqual(parse_operation(
            values(service_state="WORKAROUND", fallback_ref="SCAN-02")
        )["fallback_ref"], "SCAN-02")

    def test_result_requires_versions_and_both_preliminary_checks(self):
        variants = values(equipment_model="Scanner-A", installed_version="1.0",
                          candidate_version="2.0", rehearsal_result="PASS")
        with self.assertRaises(ValueError):
            parse_operation(values(rehearsal_result="PASS"))
        with self.assertRaises(ValueError):
            parse_operation({**variants, "pilot_result": "PASS"})
        self.assertEqual(parse_operation({
            **variants, "rollback_result": "PASS", "pilot_result": "FAIL",
        })["pilot_result"], "FAIL")

    def test_server_rejects_unexpected_fields_and_unsafe_reference_format(self):
        for record in (values(technician="another"), values(asset_ref="1234567890"),
                       values(agency_ref="<script>"), values(service_state=[])):
            with self.subTest(record=record), self.assertRaises(ValueError):
                parse_operation(record)

    def test_previous_results_cannot_be_reused_for_a_new_asset_or_version(self):
        previous = values(equipment_model="Scanner-A", installed_version="1.0",
                          candidate_version="2.0", rehearsal_result="PASS")
        for change in ({"asset_ref": "POSTE-02"}, {"candidate_version": "3.0"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_operation_update(previous, {**previous, **change})
            validate_operation_update(previous, {**previous, **change,
                                                 "rehearsal_result": "NOT_TESTED"})

    def test_interruption_and_workaround_keep_distinct_times(self):
        start = continuity_times({}, "INTERRUPTED", "09:00")
        workaround = continuity_times(
            {**start, "service_state": "INTERRUPTED"}, "WORKAROUND", "09:15"
        )
        restored = continuity_times(
            {**workaround, "service_state": "WORKAROUND"}, "RESTORED", "11:00"
        )
        self.assertEqual(restored, dict(interrupted_at="09:00", resumed_at="09:15",
                                       restored_at="11:00"))
        self.assertIsNone(continuity_times({}, "RESTORED", "11:00")["interrupted_at"])

    def test_schema_and_form_share_fields_and_choices(self):
        import re

        root = Path(__file__).resolve().parents[1]
        schema_path = root / "softsystem97/softsystem97/doctype/ss97_bank_operation/ss97_bank_operation.json"
        schema = json.loads(schema_path.read_text())
        fields = {d["fieldname"]: d for d in schema["fields"]}
        template = (root / "softsystem97/www/ss97-tech-banque.html").read_text()
        self.assertTrue(fields["mission"]["unique"])
        self.assertEqual(schema["permissions"], [{"role": "System Manager", "read": 1, "report": 1}])
        self.assertEqual(set(re.findall(r'name="([^"]+)"', template)),
                         set(REFERENCE_FIELDS) | set(CHOICES))
        for key, choices in CHOICES.items():
            self.assertEqual(fields[key]["options"].splitlines(), list(choices))
            block = re.search(rf'<select name="{key}">(.*?)</select>', template, re.S)[1]
            self.assertEqual(re.findall(r'<option value="([^"]+)">', block), list(choices))


class BankOperationAccessTests(unittest.TestCase):
    def setUp(self):
        self.frappe = types.ModuleType("frappe")
        self.frappe.whitelist = lambda **kwargs: lambda fn: fn
        self.frappe.throw = throw
        self.frappe.PermissionError = AccessDenied
        self.frappe.db = Mock()
        utils = types.ModuleType("frappe.utils")
        utils.now_datetime = lambda: "2026-11-21 15:00:00"
        self.api = types.ModuleType("softsystem97.technician_os.api")
        self.api._enabled = Mock()
        self.api._log = Mock()
        self.mission = types.SimpleNamespace(
            name="mission-1", track="BANK", technician="tech@example.invalid",
            state="IN_PROGRESS",
        )
        self.api._mission_by_id = Mock(return_value=self.mission)
        self.profile = types.SimpleNamespace(track="BANK", candidate_user=self.mission.technician)
        self.api._my_active_profile = Mock(return_value=self.profile)
        self.ticket = types.SimpleNamespace(status="Open")
        self.api._authorized_ticket = Mock(return_value=self.ticket)
        module_name = "softsystem97.technician_os.bank_operations"
        with patch.dict(sys.modules, {
            "frappe": self.frappe, "frappe.utils": utils,
            "softsystem97.technician_os.api": self.api,
        }):
            spec = importlib.util.find_spec(module_name)
            self.module = importlib.util.module_from_spec(spec)
            with patch("softsystem97.technician_os.api", self.api, create=True):
                spec.loader.exec_module(self.module)

    def test_wrong_track_or_assignment_denied_before_record_lookup(self):
        self.profile.track = "CYBER"
        with self.assertRaises(AccessDenied):
            self.module.get_bank_operation("mission-1")
        self.api._mission_by_id.assert_not_called()
        self.profile.track = "BANK"
        self.mission.technician = "other@example.invalid"
        with self.assertRaises(AccessDenied):
            self.module.get_bank_operation("mission-1")
        self.frappe.db.get_value.assert_not_called()

    def test_revoked_assignment_and_closed_ticket_prevent_write(self):
        self.api._authorized_ticket.side_effect = AccessDenied("revoked")
        with self.assertRaises(AccessDenied):
            self.module.save_bank_operation("mission-1", 0, values())
        self.api._authorized_ticket.side_effect = None
        self.ticket.status = "Closed"
        with self.assertRaises(AccessDenied):
            self.module.save_bank_operation("mission-1", 0, values())
        self.frappe.db.get_value.assert_not_called()

    def test_stale_revision_never_writes_and_valid_new_record_is_logged(self):
        self.frappe.db.get_value.return_value = None
        self.frappe.get_doc = Mock()
        with self.assertRaises(AccessDenied):
            self.module.save_bank_operation("mission-1", 1, values())
        self.frappe.get_doc.assert_not_called()

        class Record(dict):
            @property
            def revision(self):
                return self["revision"]

            def save(self, **kwargs):
                self.saved = kwargs

        record = Record()
        self.frappe.get_doc.return_value = record
        result = self.module.save_bank_operation(
            "mission-1", 0, values(service_state="INTERRUPTED")
        )
        self.assertEqual(result["revision"], 1)
        self.assertEqual(result["interrupted_at"], "2026-11-21 15:00:00")
        self.api._mission_by_id.assert_called_with("mission-1", lock=True)
        self.api._log.assert_called_once_with(
            "MISSION", "mission-1", "BANK_OPERATION_INTERRUPTED", self.mission.technician
        )


if __name__ == "__main__":
    unittest.main()
