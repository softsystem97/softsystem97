"""Read-only N2 access diagnosis regression tests; no Frappe site required."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


SOURCE = Path(__file__).resolve().parents[1] / "softsystem97/technician_readiness.py"


def load_module(fake):
    with patch.dict(sys.modules, {"frappe": fake}):
        spec = importlib.util.spec_from_file_location("ss97_n2_access_audit", SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def facade(*, admin=True, account=None, roles=(), historical=True, disabled=False):
    fake = types.ModuleType("frappe")
    fake.only_for = Mock(side_effect=None if admin else PermissionError("denied"))
    fake.throw = Mock(side_effect=ValueError("invalid input"))
    fake.db = types.SimpleNamespace(get_value=Mock(return_value=account))
    fake.get_roles = Mock(return_value=list(roles))
    rows = ([{"name": "SS97 Technician", "disabled": int(disabled)}]
            if historical else [])
    rows.append({"name": "SS97 Technicien", "disabled": 0})
    fake.get_all = Mock(return_value=rows)
    fake.db.set_value = Mock()
    fake.get_doc = Mock()
    return fake


class TestTechnicianReadiness(unittest.TestCase):
    def test_canonical_role_active_but_portal_still_unverified(self):
        fake = facade(account={"enabled": 1}, roles=["SS97 Technician"])
        status = load_module(fake).administrator_n2_access_report("n2@example.invalid")
        self.assertEqual(status["state"], "ROLE_CHECKS_PASSED_PROFILE_UNVERIFIED")
        self.assertFalse(status["technician_profile_verified"])
        self.assertFalse(status["browser_login_verified"])
        fake.db.set_value.assert_not_called()
        fake.get_doc.assert_not_called()

    def test_french_bridge_role_does_not_unlock_historical_gate(self):
        fake = facade(account={"enabled": 1}, roles=["SS97 Technicien"])
        status = load_module(fake).administrator_n2_access_report("n2@example.invalid")
        self.assertIn("HISTORICAL_ROLE_NOT_ASSIGNED", status["blockers"])
        self.assertTrue(status["bridge_role_assigned"])

    def test_disabled_account_or_role_fail_closed(self):
        fake = facade(account={"enabled": 0}, roles=["SS97 Technician"], disabled=True)
        status = load_module(fake).administrator_n2_access_report("n2@example.invalid")
        self.assertIn("USER_DISABLED", status["blockers"])
        self.assertIn("HISTORICAL_ROLE_DISABLED", status["blockers"])

    def test_absent_account_or_role_fail_closed(self):
        fake = facade(account=None, historical=False)
        status = load_module(fake).administrator_n2_access_report("missing@example.invalid")
        self.assertEqual(status["state"], "BLOCKED")
        self.assertIn("USER_MISSING", status["blockers"])
        self.assertIn("HISTORICAL_ROLE_MISSING", status["blockers"])
        fake.get_roles.assert_not_called()

    def test_admin_only_and_no_account_mutation(self):
        fake = facade(admin=False, account={"enabled": 1})
        with self.assertRaises(PermissionError):
            load_module(fake).administrator_n2_access_report("n2@example.invalid")
        fake.db.get_value.assert_not_called()
        fake.get_all.assert_not_called()

    def test_invalid_identifier_is_rejected_before_read(self):
        fake = facade(account={"enabled": 1})
        with self.assertRaises(ValueError):
            load_module(fake).administrator_n2_access_report(" ")
        fake.db.get_value.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
