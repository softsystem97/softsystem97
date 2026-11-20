"""Tests autonomes : aucune connexion SMTP, Frappe, ni ticket de production."""

import ast
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class ExamNoticeTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((ROOT / "softsystem97/technician_exams/api.py").read_text())
        funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in {"_stage_exam_notice", "_finish"}]
        self.assertEqual(len(funcs), 2)
        self.notices = []
        self.profile = types.SimpleNamespace(name="profile-1", candidate_user="candidate@invalid.test",
                                             track="L2", state="IN_REVIEW")
        self.config = {"ss97_tech_os": {"enabled": True}}
        self.frappe = types.SimpleNamespace(
            conf=self.config,
            db=types.SimpleNamespace(get_value=lambda *args, **kwargs: self.profile),
        )
        self.stage = types.ModuleType("softsystem97.technician_os.notices")
        self.stage.stage_notice = lambda p, k, event: self.notices.append((p, k, event))
        self.namespace = {"frappe": self.frappe, "now_datetime": lambda: "NOW",
                          "grade": lambda *_args: {"correct": 20, "percentage": 100, "passed": True},
                          "_snapshot": lambda *_args: [], "_answers": lambda *_args: {},
                          "_result": lambda doc: {"state": doc.state}}
        module = ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[]))
        exec(compile(module, "exam-api", "exec"), self.namespace)

    def notify(self, state, *, track="L2"):
        doc = types.SimpleNamespace(state=state, candidate_user="candidate@invalid.test",
                                    track=track, name="00000000-0000-0000-0000-000000000011")
        with patch.dict(sys.modules, {"softsystem97.technician_os.notices": self.stage}):
            self.namespace["_stage_exam_notice"](doc)
        return doc

    def test_pass_is_provisional_and_scoped_to_candidate(self):
        self.notify("PASSED")
        self.assertEqual([(k, e) for _, k, e in self.notices],
                         [("EXAM_PASSED_PROVISIONAL", "00000000-0000-0000-0000-000000000011")])

    def test_failed_and_expired_receive_different_notifications(self):
        self.notify("FAILED")
        self.notify("EXPIRED")
        self.assertEqual([item[1] for item in self.notices], ["EXAM_FAILED", "EXAM_EXPIRED"])

    def test_no_notice_when_flag_off_or_wrong_track_or_outside_review(self):
        self.config["ss97_tech_os"]["enabled"] = False
        self.notify("FAILED")
        self.config["ss97_tech_os"]["enabled"] = True
        self.notify("PASSED", track="BANK")
        self.profile.state = "ACTIVE"
        self.notify("PASSED")
        self.assertEqual(self.notices, [])

    def test_no_notice_while_exam_active(self):
        self.notify("IN_PROGRESS")
        self.assertEqual(self.notices, [])

    def test_finish_notifies_only_after_persisting_attempt(self):
        events = []
        fake_doc = types.SimpleNamespace(
            state="IN_PROGRESS", track="L2", candidate_user="candidate@invalid.test",
            name="00000000-0000-0000-0000-000000000011",
            save=lambda **_kwargs: events.append("saved"),
        )
        self.stage.stage_notice = lambda *_args: events.append("notice")
        with patch.dict(sys.modules, {"softsystem97.technician_os.notices": self.stage}):
            data = self.namespace["_finish"](fake_doc)
        self.assertEqual(events, ["saved", "notice"])
        self.assertEqual(data["state"], "PASSED")

    def test_notice_schema_contains_each_exam_outcome_and_no_attachments(self):
        schema = json.loads((ROOT / "softsystem97/softsystem97/doctype/ss97_technician_notice/ss97_technician_notice.json").read_text())
        kind = next(field for field in schema["fields"] if field["fieldname"] == "kind")
        self.assertTrue({"EXAM_PASSED_PROVISIONAL", "EXAM_FAILED", "EXAM_EXPIRED"}
                        <= set(kind["options"].splitlines()))
        notices = (ROOT / "softsystem97/technician_os/notices.py").read_text()
        self.assertIn("attachments=[]", notices)
        self.assertIn('get("enabled") is True', notices)


class ClientFlowTests(unittest.TestCase):
    def test_assets_registered_on_website_only(self):
        hook = (ROOT / "softsystem97/hooks.py").read_text()
        self.assertIn('css/ss97_client_journey.css?v=20261120-1', hook)
        self.assertIn('js/ss97_client_journey.js?v=20261120-1', hook)

    def test_existing_routes_are_used_not_recreated(self):
        js = (ROOT / "softsystem97/public/js/ss97_client_journey.js").read_text()
        for route in ('"/portail-client"', '"/ticket-libre"', '"/ouvrir-ticket/new"',
                      '"/espace-client/dashboard"'):
            self.assertIn(route, js)
        self.assertNotIn("frappe.call", js)
        self.assertNotIn('method: "POST"', js)
        for language in ("fr", "en", "es", "ht"):
            self.assertIn(f"    {language}: {{", js)
        self.assertIn("data-ss97-no-i18n", js)


if __name__ == "__main__":
    unittest.main()
