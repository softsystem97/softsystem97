"""Regression tests for fail-closed ERPNext Issue Server Script review.

These tests use no Frappe database, credentials or live site.
"""
import unittest

from softsystem97.integrations.ticket_bridge.issue_script_review import (
    approval_state, fingerprint,
)


class IssueScriptReviewRegressionTests(unittest.TestCase):
    reference = "SECURITY-REVIEW-20261121"

    def test_empty_inventory_without_approval_stays_locked(self):
        for approved, reviewed, reference in (
            (None, None, None),
            ({}, False, self.reference),
            ({}, True, None),
            ({}, True, "invalid"),
            ({"Old issue script": "0" * 64}, True, self.reference),
            ([], True, self.reference),
        ):
            with self.subTest(approved=approved, reviewed=reviewed, reference=reference):
                state = approval_state([], approved, reviewed, reference)
                self.assertFalse(state["approved"])
                self.assertEqual(state["count"], 0)
                self.assertGreater(state["unapproved"], 0)

    def test_explicitly_reviewed_empty_inventory_is_allowed(self):
        state = approval_state([], {}, True, self.reference)
        self.assertEqual(state, {"approved": True, "count": 0, "unapproved": 0})

    def test_pinned_scripts_must_match_exact_revision(self):
        scripts = [
            {"name": "Issue assignment", "doctype_event": "Before Save", "script": "pass"},
            {"name": "Issue notification", "doctype_event": "After Insert", "script": "pass"},
        ]
        approved = {s["name"]: fingerprint(s["name"], s["doctype_event"], s["script"])
                    for s in scripts}
        self.assertTrue(approval_state(scripts, approved, True, self.reference)["approved"])

        altered = [dict(s) for s in scripts]
        altered[0]["script"] = "print('changed')"
        self.assertFalse(approval_state(altered, approved, True, self.reference)["approved"])

        self.assertFalse(approval_state(scripts[:1], approved, True, self.reference)["approved"])
        self.assertFalse(approval_state(scripts, {scripts[0]["name"]: approved[scripts[0]["name"]]},
                                        True, self.reference)["approved"])
        self.assertFalse(approval_state(scripts, approved, False, self.reference)["approved"])


if __name__ == "__main__":
    unittest.main()
