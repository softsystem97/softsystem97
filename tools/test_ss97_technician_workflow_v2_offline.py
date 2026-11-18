"""Regression gates for candidate self-service, email queue and settlement safety."""

import ast
import importlib
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from softsystem97.technician_os.training import COURSES, course_for_track


ROOT = Path(__file__).resolve().parents[1]


class TechnicianWorkflowV2Tests(unittest.TestCase):
    def test_guest_signup_link_uses_existing_login_signup_form(self):
        source = (ROOT / "softsystem97/www/ss97-tech-os.html").read_text(encoding="utf-8")
        self.assertIn('/login?redirect-to=%2Fss97-tech-os#signup', source)
        self.assertNotIn('href="/signup?', source)

    def test_training_not_mixed_across_tracks(self):
        self.assertEqual(set(COURSES), {"L2", "BANK", "CYBER"})
        for track in COURSES:
            with self.subTest(track=track):
                lessons = course_for_track(track)
                self.assertEqual(len(lessons), 6)
                self.assertEqual([lesson["number"] for lesson in lessons], list(range(1, 7)))
                self.assertTrue(all(lesson["title"] and lesson["objective"] for lesson in lessons))
        self.assertNotEqual(COURSES["L2"], COURSES["BANK"])
        self.assertNotEqual(COURSES["BANK"], COURSES["CYBER"])

    def test_training_unknown_track_fails_closed(self):
        with self.assertRaises(ValueError):
            course_for_track("N5")

    def test_self_enrollment_rejects_clients_and_multiple_track_roles(self):
        fake_frappe = types.ModuleType("frappe")
        fake_frappe.__path__ = []
        fake_frappe.get_roles = lambda _user: ["All", "Website User", "Customer"]
        fake_frappe.db = types.SimpleNamespace(
            get_value=lambda *_args: "Website User",
        )
        fake_frappe.whitelist = lambda **_kw: lambda func: func
        fake_utils = types.ModuleType("frappe.utils")
        fake_utils.now_datetime = lambda: None
        fake_frappe.utils = fake_utils
        with patch.dict(sys.modules, {"frappe": fake_frappe, "frappe.utils": fake_utils}):
            module = importlib.import_module("softsystem97.technician_os.api")
            try:
                self.assertFalse(module._can_apply("person@example.test"))
                fake_frappe.get_roles = lambda _user: ["All", "Website User", "SS97 Technicien N4"]
                self.assertFalse(module._can_apply("person@example.test"))
                fake_frappe.get_roles = lambda _user: ["All", "Website User"]
                self.assertTrue(module._can_apply("person@example.test"))
                fake_frappe.db.get_value = lambda *_args: "System User"
                self.assertFalse(module._can_apply("person@example.test"))
            finally:
                sys.modules.pop("softsystem97.technician_os.api", None)
                sys.modules.pop("softsystem97.technician_os.notices", None)

    def test_private_doctypes_only_manager_can_read(self):
        for name in ("ss97_technician_document", "ss97_technician_notice",
                     "ss97_technician_settlement"):
            with self.subTest(name=name):
                path = ROOT / f"softsystem97/softsystem97/doctype/{name}/{name}.json"
                schema = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(schema["permissions"], [{
                    "role": "System Manager", "read": 1, "report": 1,
                }])

    def test_settlement_unique_mission_and_no_bank_details(self):
        path = (ROOT / "softsystem97/softsystem97/doctype/ss97_technician_settlement"
                / "ss97_technician_settlement.json")
        schema = json.loads(path.read_text(encoding="utf-8"))
        mission = next(field for field in schema["fields"] if field["fieldname"] == "mission")
        self.assertEqual(mission["unique"], 1)
        self.assertEqual(set(next(field for field in schema["fields"]
                                  if field["fieldname"] == "state")["options"].splitlines()),
                         {"REVIEW_REQUIRED", "APPROVED"})
        self.assertFalse(any(field["fieldname"] in {"rib", "iban", "bank_account"}
                             for field in schema["fields"]))

    def test_settlement_explicit_dual_approval_no_payout_method(self):
        source = (ROOT / "softsystem97/technician_os/api.py").read_text(encoding="utf-8")
        functions = {n.name for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)}
        self.assertTrue({"prepare_settlement", "approve_settlement"} <= functions)
        self.assertIn('"reviewed_by": reviewer, "state": "VERIFIED"', source)
        self.assertIn('mission.state != "CLIENT_ACCEPTED"', source)
        self.assertIn("manager in {settlement.prepared_by, mission.technician, mission.created_by_user}", source)
        self.assertNotIn("stripe.Transfer.create", source)
        self.assertNotIn("payouts.create", source)
        self.assertNotIn("create_payout", source)

    def test_mail_outbox_requires_enabled_flag_and_never_includes_private_files(self):
        source = (ROOT / "softsystem97/technician_os/notices.py").read_text(encoding="utf-8")
        self.assertIn('get("enabled") is True', source)
        self.assertIn("enqueue_after_commit=True", source)
        self.assertIn("delayed=True", source)
        self.assertIn("attachments=[]", source)
        self.assertIn('notice.state = "QUEUED"', source)
        self.assertNotIn("DELIVERED", source)
        self.assertNotIn("allow_guest=True", source)

    def test_notices_use_one_key_per_recorded_transition(self):
        path = (ROOT / "softsystem97/softsystem97/doctype/ss97_technician_notice"
                / "ss97_technician_notice.json")
        schema = json.loads(path.read_text(encoding="utf-8"))
        key = next(field for field in schema["fields"] if field["fieldname"] == "event_key")
        self.assertEqual(key["unique"], 1)
        self.assertIn("HELD", next(field for field in schema["fields"]
                                   if field["fieldname"] == "state")["options"])

    def test_notice_retry_never_sends_when_flag_is_off(self):
        source = (ROOT / "softsystem97/technician_os/api.py").read_text(encoding="utf-8")
        self.assertIn('def retry_candidate_notice(notice_id):', source)
        self.assertIn('if not _mail_enabled():', source)
        self.assertIn('if notice.state not in {"HELD", "ERROR"}:', source)


if __name__ == "__main__":
    unittest.main()
