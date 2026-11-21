"""No-site regression checks for native Issue technician isolation."""

import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class IssuePermissionsOfflineTests(unittest.TestCase):
    def setUp(self):
        self.roles = {}
        self.approved = set()
        self.enabled = True
        self.schema_ready = True
        self.historical_enabled = False
        self.sql_calls = []

        fake = types.ModuleType("frappe")
        fake.__path__ = []
        fake.session = types.SimpleNamespace(user="tech@example.test")
        fake.conf = {"ss97_ticket_bridge": {"enabled": True}}
        fake.get_roles = lambda user: self.roles.get(user, [])
        fake.db = types.SimpleNamespace(
            table_exists=lambda _name: self.schema_ready,
            escape=lambda value: "'" + value.replace("'", "''") + "'",
        )
        fake.get_meta = lambda _name: types.SimpleNamespace(has_field=lambda _field: self.schema_ready)
        self.fake = fake
        self.imports = patch.dict(sys.modules, {"frappe": fake})
        self.imports.start()
        sys.modules.pop("softsystem97.portal.issue_permissions", None)
        self.module = importlib.import_module("softsystem97.portal.issue_permissions")
        self.p1 = patch.object(self.module.historical, "enabled", lambda: self.historical_enabled)
        self.p2 = patch.object(self.module.policy, "approved_assignment_query", lambda: "FROM `tabToDo` t WHERE t.status = 'Open'")
        self.p3 = patch.object(self.module.policy, "assigned", lambda name, user: (name, user) in self.approved)
        for p in (self.p1, self.p2, self.p3):
            p.start()

    def tearDown(self):
        for p in (self.p3, self.p2, self.p1):
            p.stop()
        sys.modules.pop("softsystem97.portal.issue_permissions", None)
        self.imports.stop()

    def test_n2_list_is_approved_only_and_escape_user(self):
        user = "o'reilly@example.test"
        self.roles[user] = ["SS97 Technician", "SS97 Technicien N2"]
        query = self.module.get_permission_query_conditions(user)
        self.assertIn("t.reference_name = `tabIssue`.`name`", query)
        self.assertIn("t.allocated_to = 'o''reilly@example.test'", query)
        self.assertNotIn(" OR ", query)

    def test_approval_cannot_grant_more_than_native_rights(self):
        user = "tech@example.test"
        doc = types.SimpleNamespace(name="ISSUE-001")
        self.roles[user] = ["SS97 Technician"]
        self.assertIs(self.module.has_permission(doc, "read", user), False)
        self.assertIs(self.module.has_permission(doc, "write", user), False)
        self.approved.add((doc.name, user))
        self.assertIs(self.module.has_permission(doc, "read", user), True)
        self.assertIs(self.module.has_permission(doc, "write", user), True)
        self.assertIs(self.module.has_permission(doc, "delete", user), True)

    def test_bridge_off_or_incomplete_schema_fails_closed(self):
        self.roles["tech@example.test"] = ["SS97 Technician"]
        for key in ("enabled", "schema_ready"):
            with self.subTest(key=key):
                original = getattr(self, key)
                setattr(self, key, False)
                self.fake.conf["ss97_ticket_bridge"]["enabled"] = self.enabled
                self.assertEqual(self.module.get_permission_query_conditions(), "1=0")
                self.assertFalse(self.module.has_permission(types.SimpleNamespace(name="X"), "read"))
                setattr(self, key, original)
                self.fake.conf["ss97_ticket_bridge"]["enabled"] = self.enabled

    def test_other_users_retain_native_permissions(self):
        for user, roles in (("staff@example.test", ["System Manager", "SS97 Technician"]),
                            ("client@example.test", ["Customer"]),
                            ("Guest", [])):
            with self.subTest(user=user):
                self.roles[user] = roles
                self.assertEqual(self.module.get_permission_query_conditions(user), "")
                self.assertIs(self.module.has_permission(types.SimpleNamespace(name="X"), user=user), True)

    def test_hooks_register_both_list_and_document_guards(self):
        hooks = (ROOT / "softsystem97/hooks.py").read_text(encoding="utf-8")
        self.assertIn('"Issue": "softsystem97.portal.issue_permissions.get_permission_query_conditions"', hooks)
        self.assertIn('"Issue": "softsystem97.portal.issue_permissions.has_permission"', hooks)


if __name__ == "__main__":
    unittest.main()
