"""Offline checks for the unified N2 / banking / cyber remote authorization."""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

# Shared fake Frappe module, never a live database or an external connection.
from tools.test_remote_api_offline import PermissionDenied, api, frappe

# The shared fake-Frappe loader removes temporary sys.modules entries after
# import. Keep a view of the actual function-global references.
access = SimpleNamespace(**api.authorize_technician_ticket.__globals__)
with patch.dict(sys.modules, {"frappe": frappe, "softsystem97.remote.api": api}):
    from softsystem97.remote import lifecycle


class TestRemoteMissionRules(unittest.TestCase):
    def setUp(self):
        self.ticket = SimpleNamespace(name="ISS-1", status="Open", customer="ACME",
                                      raised_by="client@a.invalid")
        self.profile = SimpleNamespace(candidate_user="tech@ss97.invalid", track="L2",
                                       state="ACTIVE", engagement="FREELANCE")
        self.mission = SimpleNamespace(name="MISSION-1", ticket_name="ISS-1", customer="ACME",
                                       technician="tech@ss97.invalid", track="L2",
                                       state="IN_PROGRESS", accepted_at="2026-11-19 12:00",
                                       authorization_reference="", approved_by="",
                                       created_by_user="manager@ss97.invalid")

    def test_all_tracks_can_use_one_coordinator_with_correct_mission(self):
        for track in ("L2", "BANK", "CYBER"):
            self.profile.track = self.mission.track = track
            if track != "L2":
                self.mission.authorization_reference = "auth-12345"
                self.mission.approved_by = "approver@ss97.invalid"
            self.assertTrue(access.check_mission(
                self.ticket, "tech@ss97.invalid", self.profile, self.mission))

    def test_mission_must_be_in_progress_and_explicitly_accepted(self):
        for state in ("OFFERED", "PENDING_APPROVAL", "ACCEPTED", "REPORT_SUBMITTED", "CANCELLED"):
            self.mission.state = state
            self.assertFalse(access.check_mission(
                self.ticket, "tech@ss97.invalid", self.profile, self.mission))
        self.mission.state = "IN_PROGRESS"
        self.mission.accepted_at = None
        self.assertFalse(access.check_mission(
            self.ticket, "tech@ss97.invalid", self.profile, self.mission))

    def test_cross_customer_cross_track_or_other_technician_denied(self):
        self.mission.customer = "OTHER"
        self.assertFalse(access.check_mission(
            self.ticket, "tech@ss97.invalid", self.profile, self.mission))
        self.mission.customer = "ACME"
        self.mission.track = "CYBER"
        self.assertFalse(access.check_mission(
            self.ticket, "tech@ss97.invalid", self.profile, self.mission))
        self.mission.track = "L2"
        self.assertFalse(access.check_mission(
            self.ticket, "other@ss97.invalid", self.profile, self.mission))

    def test_bank_and_cyber_require_independent_approval_and_scope(self):
        for track in ("BANK", "CYBER"):
            self.profile.track = self.mission.track = track
            self.mission.authorization_reference = ""
            self.mission.approved_by = "approver@ss97.invalid"
            self.assertFalse(access.check_mission(
                self.ticket, "tech@ss97.invalid", self.profile, self.mission))
            self.mission.authorization_reference = "scope-12345"
            self.mission.approved_by = self.mission.created_by_user
            self.assertFalse(access.check_mission(
                self.ticket, "tech@ss97.invalid", self.profile, self.mission))

    def test_sensitive_support_excludes_client_from_mandate_approval(self):
        for track in ("BANK", "CYBER"):
            self.profile.track = self.mission.track = track
            self.mission.authorization_reference = "original-mandate"
            self.mission.approved_by = self.ticket.raised_by
            self.assertFalse(access.check_mission(
                self.ticket, self.mission.technician, self.profile, self.mission))

    def test_sensitive_rework_requires_fresh_mandate_and_approval(self):
        for track in ("BANK", "CYBER"):
            self.profile.track = self.mission.track = track
            self.mission.authorization_reference = "original-mandate"
            self.mission.approved_by = "approver@ss97.invalid"
            self.mission.rework_count = 1
            self.mission.rework_requested_at = "2026-11-19 12:30"
            self.mission.rework_requested_by = "manager@ss97.invalid"
            self.mission.rework_approved_at = None
            self.assertFalse(access.check_mission(
                self.ticket, self.mission.technician, self.profile, self.mission))
            self.mission.rework_authorization_reference = "rework-mandate"
            self.mission.rework_approved_at = "2026-11-19 12:45"
            self.mission.rework_approved_by = self.mission.rework_requested_by
            self.assertFalse(access.check_mission(
                self.ticket, self.mission.technician, self.profile, self.mission))
            self.mission.rework_approved_by = "approver@ss97.invalid"
            self.assertTrue(access.check_mission(
                self.ticket, self.mission.technician, self.profile, self.mission))

    def test_complete_authorization_requires_profile_role_assignment_and_mission(self):
        db = SimpleNamespace(get_value=lambda *args, **kwargs: 1,
                             exists=lambda *args, **kwargs: True)
        role = "SS97 Technicien N2"
        with patch.object(access.frappe, "db", db, create=True), patch.object(
                access.frappe, "get_roles", lambda user: [role], create=True), patch.object(
                access.frappe, "get_all", return_value=[SimpleNamespace(name="MISSION-1")], create=True), patch.object(
                access.frappe, "get_doc", return_value=self.mission, create=True), patch.object(
                access.frappe, "session", SimpleNamespace(user="tech@ss97.invalid")), patch.object(
                access.policy, "settings"), patch.object(
                access.policy, "assigned", return_value=True) as assignment, patch.object(
                access.policy, "client_customer_for_user", return_value="ACME"), patch.object(
                access.technician_os, "_enabled"), patch.object(
                access.technician_os, "_profile_for_user", return_value=self.profile):
            self.assertEqual(access.authorize_technician_ticket(self.ticket),
                             ("tech@ss97.invalid", "L2"))
            self.profile.state = "SUSPENDED"
            with self.assertRaises(PermissionDenied):
                access.authorize_technician_ticket(self.ticket)
            self.profile.state = "ACTIVE"
            assignment.return_value = False
            with self.assertRaises(PermissionDenied):
                access.authorize_technician_ticket(self.ticket)

    def test_accounting_or_admin_roles_block_remote_operator(self):
        db = SimpleNamespace(get_value=lambda *args, **kwargs: 1,
                             exists=lambda *args, **kwargs: True)
        with patch.object(access.frappe, "db", db, create=True), patch.object(
                access.frappe, "get_roles", return_value=["SS97 Technicien N2", "Accounts Manager"], create=True), patch.object(
                access.frappe, "session", SimpleNamespace(user="tech@ss97.invalid")), patch.object(
                access.policy, "settings"), patch.object(
                access.technician_os, "_enabled"), patch.object(
                access.technician_os, "_profile_for_user", return_value=self.profile):
            with self.assertRaises(PermissionDenied):
                access.authorize_technician_ticket(self.ticket)


class TestRemoteInvitationRevocation(unittest.TestCase):
    def test_deleting_open_ticket_revokes_pending_invitations(self):
        ticket = SimpleNamespace(name="ISS-1", status="Open")
        with patch.object(lifecycle, "_available", return_value=True), patch.object(
                lifecycle, "_end_pending") as revoke:
            lifecycle.revoke_on_issue_close(ticket, "on_trash")
        revoke.assert_called_once_with("ISS-1")

    def test_changing_mandate_revokes_pending_invitation(self):
        before = {"ticket_name": "ISS-1", "technician": "tech@example.invalid",
                  "authorization_reference": "original"}
        after = {**before, "authorization_reference": "new"}
        previous = SimpleNamespace(**before, get=before.get)
        mission = SimpleNamespace(**after, state="IN_PROGRESS", get=after.get,
                                  get_doc_before_save=lambda: previous)
        with patch.object(lifecycle, "_available", return_value=True), patch.object(
                lifecycle, "_end_pending") as revoke:
            lifecycle.revoke_on_mission_change(mission)
            revoke.assert_called_once_with("ISS-1", "tech@example.invalid")
            revoke.reset_mock()
            mission.get = before.get
            lifecycle.revoke_on_mission_change(mission)
            revoke.assert_not_called()


if __name__ == "__main__":
    unittest.main()
