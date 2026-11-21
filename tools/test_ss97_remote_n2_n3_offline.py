"""Offline regression tests for N2/N3 remote support authorization.

Synthetic users and tickets only. No remote connection, Frappe site, or credentials.
"""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from softsystem97.technician_os.remote_access_rules import (
    RemoteAccessDenied, RemoteAccessEvidence, authorize_remote_start,
)

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def evidence(track="L2"):
    return RemoteAccessEvidence(
        track=track, ticket="ISSUE-SYNTHETIC-01", device="DEVICE-SYNTHETIC-01",
        technician="tech@example.invalid", customer="client@example.invalid",
        profile_state="ACTIVE", technician_enabled=True, ticket_open=True,
        assigned_technician="tech@example.invalid", assignment_approved=True,
        technician_roles=("SS97 Technicien N2",) if track == "L2" else ("SS97 Technicien N3",),
        consenting_user="client@example.invalid",
        consent_ticket="ISSUE-SYNTHETIC-01",
        consent_device="DEVICE-SYNTHETIC-01",
        consent_technician="tech@example.invalid",
        consent_at=NOW - timedelta(minutes=2), expires_at=NOW + timedelta(minutes=20),
        now=NOW, mandate_reference="BANK-AUTH-001",
        mandate_ticket="ISSUE-SYNTHETIC-01",
        mandate_device="DEVICE-SYNTHETIC-01",
        mandate_technician="tech@example.invalid",
        manager_approvals=("manager1@example.invalid", "manager2@example.invalid"),
    )


class RemoteSupportRulesTests(unittest.TestCase):
    def deny(self, item):
        with self.assertRaises(RemoteAccessDenied):
            authorize_remote_start(item)

    def test_n2_valid_session_has_no_remote_token_or_secret(self):
        data = authorize_remote_start(evidence())
        self.assertEqual(data["track"], "L2")
        self.assertEqual(data["ticket"], "ISSUE-SYNTHETIC-01")
        self.assertEqual(set(data), {"authorized", "track", "ticket", "device", "expires_at"})
        self.assertNotIn("token", str(data).lower())
        self.assertNotIn("password", str(data).lower())

    def test_n3_requires_mandate_and_independent_dual_approval(self):
        self.assertTrue(authorize_remote_start(evidence("BANK"))["authorized"])
        for overrides in (
            {"mandate_reference": ""},
            {"mandate_ticket": "OTHER-ISSUE"},
            {"mandate_device": "OTHER-DEVICE"},
            {"mandate_technician": "other@example.invalid"},
            {"manager_approvals": ()},
            {"manager_approvals": ("manager1@example.invalid",)},
            {"manager_approvals": ("manager1@example.invalid", "manager1@example.invalid")},
            {"manager_approvals": ("tech@example.invalid", "manager2@example.invalid")},
            {"manager_approvals": ("client@example.invalid", "manager2@example.invalid")},
        ):
            with self.subTest(overrides=overrides):
                self.deny(replace(evidence("BANK"), **overrides))

    def test_n4_cannot_implicitly_use_n2_n3_remote_gate(self):
        self.deny(replace(evidence(), track="CYBER"))

    def test_role_is_specialty_exclusive_not_legacy_or_elevated(self):
        for roles in (
            ("SS97 Technician",), ("SS97 Technicien N3",),
            ("SS97 Technicien N2", "SS97 Technicien N3"), (),
        ):
            with self.subTest(roles=roles):
                self.deny(replace(evidence(), technician_roles=roles))

    def test_disabled_user_and_suspended_or_unreviewed_profile_denied(self):
        for overrides in (
            {"technician_enabled": False}, {"profile_state": "SUSPENDED"},
            {"profile_state": "IN_REVIEW"}, {"ticket_open": False},
            {"assignment_approved": False},
            {"assigned_technician": "someone@example.invalid"},
        ):
            with self.subTest(overrides=overrides):
                self.deny(replace(evidence(), **overrides))

    def test_consent_must_bind_ticket_device_and_real_client(self):
        for overrides in (
            {"consenting_user": "someone@example.invalid"},
            {"consent_ticket": "ISSUE-OTHER"},
            {"consent_device": "DEVICE-OTHER"},
            {"consent_technician": "other@example.invalid"},
            {"customer": "tech@example.invalid"},
        ):
            with self.subTest(overrides=overrides):
                self.deny(replace(evidence(), **overrides))

    def test_consent_revocation_or_closed_session_denies(self):
        self.deny(replace(evidence(), consent_revoked=True))
        self.deny(replace(evidence(), session_closed=True))

    def test_time_limits_prevent_expiry_replay_and_future_consent(self):
        for overrides in (
            {"consent_at": NOW - timedelta(minutes=16)},
            {"consent_at": NOW + timedelta(seconds=1)},
            {"expires_at": NOW},
            {"expires_at": NOW - timedelta(seconds=1)},
            {"expires_at": NOW + timedelta(minutes=61)},
            {"now": NOW.replace(tzinfo=None)},
        ):
            with self.subTest(overrides=overrides):
                self.deny(replace(evidence(), **overrides))
        self.deny(replace(evidence("BANK"), expires_at=NOW + timedelta(minutes=31)))

    def test_n3_role_must_be_n3_even_with_dual_approval(self):
        self.deny(replace(evidence("BANK"), technician_roles=("SS97 Technicien N2",)))

    def test_manager_cannot_be_customer_or_technician_even_if_distinct(self):
        self.deny(replace(evidence("BANK"), manager_approvals=(
            "client@example.invalid", "manager2@example.invalid")))
        self.deny(replace(evidence("BANK"), manager_approvals=(
            "tech@example.invalid", "manager2@example.invalid")))


if __name__ == "__main__":
    unittest.main()
