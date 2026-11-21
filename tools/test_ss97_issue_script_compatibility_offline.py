"""Pure tests for exact, signed-off Issue Server Script revisions."""
import unittest
from pathlib import Path
from softsystem97.integrations.ticket_bridge.issue_script_review import (
    fingerprint, approval_state,
)

ROOT = Path(__file__).resolve().parents[1]


class IssueScriptCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.scripts = [
            {"name": "SS97 Issue Hook A", "doctype_event": "Before Save",
             "script": "doc.subject = doc.subject"},
            {"name": "SS97 Issue Hook B", "doctype_event": "After Save",
             "script": "pass"},
        ]
        self.allow = {x["name"]: fingerprint(x["name"], x["doctype_event"], x["script"])
                      for x in self.scripts}

    def check(self, scripts=None, approved=None, reviewed=True, reference="SS97-ISSUE-REVIEW-2026"):
        return approval_state(self.scripts if scripts is None else scripts,
                              self.allow if approved is None else approved,
                              reviewed, reference)

    def test_no_scripts_is_safe(self):
        self.assertTrue(self.check(scripts=[], reviewed=False, approved={})["approved"])

    def test_exact_reviewed_versions(self):
        self.assertTrue(self.check()["approved"])
        self.assertEqual(self.check()["count"], 2)

    def test_refuses_unreviewed(self):
        self.assertFalse(self.check(reviewed=False)["approved"])
        self.assertFalse(self.check(reference="short")["approved"])

    def test_script_edit_forces_lock(self):
        altered = [dict(s) for s in self.scripts]
        altered[0]["script"] += "  # changed"
        self.assertFalse(self.check(scripts=altered)["approved"])

    def test_event_edit_forces_lock(self):
        altered = [dict(s) for s in self.scripts]
        altered[0]["doctype_event"] = "Before Insert"
        self.assertFalse(self.check(scripts=altered)["approved"])

    def test_unknown_script_forces_lock(self):
        altered = self.scripts + [{"name":"Third","doctype_event":"Before Save","script":"pass"}]
        self.assertFalse(self.check(scripts=altered)["approved"])

    def test_deleted_script_forces_lock(self):
        self.assertFalse(self.check(scripts=self.scripts[:1])["approved"])

    def test_duplicate_and_invalid_hash_forces_lock(self):
        self.assertFalse(self.check(scripts=self.scripts+self.scripts)["approved"])
        self.assertFalse(self.check(approved={**self.allow,
            "SS97 Issue Hook A": "invalid"})["approved"])

    def test_policy_and_admin_preflight(self):
        policy=(ROOT/"softsystem97/integrations/ticket_bridge/policy.py").read_text()
        readiness=(ROOT/"softsystem97/integrations/ticket_bridge/readiness.py").read_text()
        self.assertIn("issue_script_review.inventory(frappe)", policy)
        self.assertIn("if not approval['approved']", policy)
        self.assertIn("issue_script_review.inventory(frappe)", readiness)
        self.assertIn('"issue_scripts_approved"', readiness)
        self.assertNotIn("frappe.db.set_value(", readiness)
        self.assertNotIn('methods=["POST"]', readiness)

if __name__ == "__main__":
    unittest.main()
