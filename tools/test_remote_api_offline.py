"""Authorization regression tests with fake Frappe; not a live-site substitute."""

import importlib
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class PermissionDenied(Exception):
    pass


def _load_api():
    frappe = types.ModuleType("frappe")
    frappe.PermissionError = PermissionDenied
    frappe.whitelist = lambda **kwargs: lambda fn: fn
    frappe.throw = lambda message, *args: (_ for _ in ()).throw(PermissionDenied(message))
    frappe.conf = {"encryption_key": "test-key-" * 6}
    frappe.session = SimpleNamespace(user="test@example.invalid")
    utils = types.ModuleType("frappe.utils")
    utils.get_datetime = lambda value: value
    utils.now_datetime = lambda: __import__("datetime").datetime(2026, 11, 17)
    with patch.dict(sys.modules, {"frappe": frappe, "frappe.utils": utils}):
        return importlib.import_module("softsystem97.remote.api"), frappe


api, frappe = _load_api()


class TestRemoteApiAuthorizations(unittest.TestCase):
    def setUp(self):
        self.ticket = SimpleNamespace(name="ISS-1", customer="ACME", raised_by="client@a.invalid")
        self.session = SimpleNamespace(ticket_name="ISS-1", customer="ACME",
            client_user="client@a.invalid", technician="tech@ss97.invalid")

    def test_assigned_technician_matches_session_identity(self):
        with patch.object(api, "_issue", return_value=self.ticket), patch.object(
                api.policy, "authorize", return_value="tech@ss97.invalid"):
            self.assertEqual(api._authorized(self.session, "technician"), "tech@ss97.invalid")

    def test_other_assigned_technician_cannot_steal_session(self):
        with patch.object(api, "_issue", return_value=self.ticket), patch.object(
                api.policy, "authorize", return_value="other-tech@ss97.invalid"):
            with self.assertRaises(PermissionDenied):
                api._authorized(self.session, "technician")

    def test_other_customer_cannot_see_session(self):
        with patch.object(api, "_issue", return_value=self.ticket), patch.object(
                api.policy, "authorize", return_value="client@b.invalid"):
            with self.assertRaises(PermissionDenied):
                api._authorized(self.session, "client")

    def test_ticket_customer_reassignment_revokes_session(self):
        self.ticket.customer = "OTHER COMPANY"
        with patch.object(api, "_issue", return_value=self.ticket), patch.object(
                api.policy, "authorize", return_value="tech@ss97.invalid"):
            with self.assertRaises(PermissionDenied):
                api._authorized(self.session, "technician")

    def test_native_authorizer_deny_stays_deny(self):
        with patch.object(api, "_issue", return_value=self.ticket), patch.object(
                api.policy, "authorize", side_effect=PermissionDenied("not assigned")):
            with self.assertRaises(PermissionDenied):
                api._authorized(self.session, "technician")

    def test_unknown_audience_denied_before_read(self):
        with patch.object(api, "_settings", return_value="test-key-" * 6), patch.object(
                api, "_session") as lookup:
            with self.assertRaises(PermissionDenied):
                api.get_session("some-id", "anonymous")
            lookup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
