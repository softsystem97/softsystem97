"""Offline N4 mission pilot contracts: no real users, tickets or payments."""
import ast
import unittest
from pathlib import Path

from softsystem97.technician_os.rules import (
    exact_track_role, next_mission_state, next_profile_state,
)

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "softsystem97" / "technician_os" / "api.py"


class N4MissionPilotTests(unittest.TestCase):
    def test_profile_requires_ordered_human_review(self):
        states = (
            "APPLIED", "IN_REVIEW", "EXAM_VALIDATED", "DOCUMENTS_VALIDATED",
            "CONTRACT_SIGNED", "ACTIVE",
        )
        for old, new in zip(states, states[1:]):
            self.assertTrue(next_profile_state(old, new), (old, new))
        self.assertFalse(next_profile_state("APPLIED", "ACTIVE"))
        self.assertFalse(next_profile_state("IN_REVIEW", "ACTIVE"))

    def test_role_only_does_not_confer_n4(self):
        self.assertTrue(exact_track_role(["SS97 Technicien N4", "All"], "CYBER"))
        self.assertFalse(exact_track_role(["SS97 Technicien N3", "All"], "CYBER"))
        self.assertFalse(exact_track_role(
            ["SS97 Technicien N4", "SS97 Technicien N2"], "CYBER"))
        self.assertFalse(exact_track_role([], "CYBER"))

    def test_suspension_blocks_direct_reactivation_without_review(self):
        self.assertTrue(next_profile_state("ACTIVE", "SUSPENDED"))
        self.assertFalse(next_profile_state("REJECTED", "ACTIVE"))
        self.assertFalse(next_profile_state("ACTIVE", "ACTIVE"))

    def test_mission_happy_path_reaches_client_acceptance(self):
        states = ("PENDING_APPROVAL", "OFFERED", "ACCEPTED", "IN_PROGRESS",
                  "REPORT_SUBMITTED", "CLIENT_ACCEPTED")
        for old, new in zip(states, states[1:]):
            self.assertTrue(next_mission_state(old, new), (old, new))
        self.assertFalse(next_mission_state("OFFERED", "REPORT_SUBMITTED"))
        self.assertFalse(next_mission_state("IN_PROGRESS", "CLIENT_ACCEPTED"))

    def test_dispute_cannot_be_paid_or_accepted_without_new_report(self):
        self.assertTrue(next_mission_state("REPORT_SUBMITTED", "DISPUTED"))
        self.assertFalse(next_mission_state("DISPUTED", "CLIENT_ACCEPTED"))
        self.assertFalse(next_mission_state("DISPUTED", "REPORT_SUBMITTED"))
        self.assertFalse(next_mission_state("DISPUTED", "OFFERED"))

    def test_closed_mission_is_terminal(self):
        for state in ("CLIENT_ACCEPTED", "CANCELLED", "DECLINED"):
            self.assertFalse(next_mission_state(state, "IN_PROGRESS"))
            self.assertFalse(next_mission_state(state, "REPORT_SUBMITTED"))

    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(API.read_text(encoding="utf-8"))
        cls.functions = {
            node.name: ast.get_source_segment(API.read_text(encoding="utf-8"), node)
            for node in cls.tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    def test_n4_offer_requires_manager_and_approved_assignment(self):
        body = self.functions["offer_mission"]
        self.assertIn("coordinator = _manager()", body)
        self.assertIn("policy.assigned(", body)
        self.assertIn("profile.state != \"ACTIVE\"", body)
        self.assertIn('state = "PENDING_APPROVAL" if profile.track in SENSITIVE_TRACKS', body)
        self.assertIn("authorization_reference", body)

    def test_sensitive_mission_requires_independent_approval(self):
        body = self.functions["approve_sensitive_mission"]
        self.assertIn("approver = _manager()", body)
        self.assertIn('mission.state != "PENDING_APPROVAL"', body)
        self.assertIn("mission.created_by_user == approver", body)
        self.assertIn("mission.technician == approver", body)
        self.assertIn("_active_assignment_ticket(mission)", body)

    def test_client_report_review_checks_ticket_and_identity(self):
        body = self.functions["review_client_report"]
        self.assertIn("_authorized_ticket(mission, \"client\")", body)
        self.assertIn("client_user == mission.technician", body)
        self.assertIn('decision not in {"CLIENT_ACCEPTED", "DISPUTED"}', body)

    def test_sensitive_rework_requires_second_manager_and_mandate(self):
        request = self.functions["request_dispute_rework"]
        approval = self.functions["approve_sensitive_rework"]
        self.assertIn('mission.state != "DISPUTED"', request)
        self.assertIn('mission.state = "REWORK_PENDING_APPROVAL"', request)
        self.assertIn("rework_authorization_reference", request)
        self.assertIn("mission.rework_requested_by = manager", request)
        self.assertIn('mission.state != "REWORK_PENDING_APPROVAL"', approval)
        self.assertIn("mission.rework_requested_by, mission.technician", approval)
        self.assertIn("not mission.rework_authorization_reference", approval)
        self.assertIn("mission.state = \"IN_PROGRESS\"", approval)

    def test_financial_review_requires_client_accepted(self):
        body = self.functions["prepare_settlement"]
        self.assertIn('mission.state != "CLIENT_ACCEPTED"', body)
        self.assertIn("mission.client_accepted_at", body)
        approve = self.functions["approve_settlement"]
        self.assertIn("_manager()", approve)
        self.assertNotIn("bank.transfer", approve.lower())


if __name__ == "__main__":
    unittest.main()
