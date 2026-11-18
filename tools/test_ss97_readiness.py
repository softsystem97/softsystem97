"""Offline tests for SS97 readiness."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "softsystem97/integrations/ticket_bridge/readiness.py"
)


def fake_frappe(admin=True, enabled=True):
    fake = types.ModuleType("frappe")
    fake.whitelist = lambda methods: lambda func: func
    fake.only_for = Mock(
        side_effect=None if admin else PermissionError("Denied")
    )

    fake.conf = {
        "ss97_ticket_bridge": {
            "enabled": enabled,
            "historical_integration": True,
            "technician_role": "SS97 Technician",
            "profile_required": False,
            "business_authorizer":
                "softsystem97.integrations.ticket_bridge.safe_provider"
        }
    }

    fake.db = Mock()
    fake.get_meta = Mock()
    fake.db.exists.side_effect = lambda name, *_: name == "Role"

    fake.get_meta.return_value.get_field.return_value = (
        types.SimpleNamespace(fieldtype="Link", options="User")
    )

    return fake


def run(fake):
    with patch.dict(sys.modules, {"frappe": fake}):
        spec = importlib.util.spec_from_file_location(
            "ss97_phase5_readiness", SOURCE
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.get_readiness()


class TestReadiness(unittest.TestCase):

    def test_admin_required(self):
        fake = fake_frappe(admin=False)
        with self.assertRaises(PermissionError):
            run(fake)
        fake.db.exists.assert_not_called()

    def test_read_only_checks(self):
        fake = fake_frappe()
        result = run(fake)
        self.assertTrue(result["checks"]["technician_field_valid"])
        self.assertFalse(result["production_ready"])
        self.assertIn(
            "payment_ticket_link_verified",
            result["blockers"]
        )
        fake.db.set_value.assert_not_called()

    def test_disabled_bridge(self):
        result = run(fake_frappe(enabled=False))
        self.assertIn("bridge_enabled", result["blockers"])

    def test_private_errors_hidden(self):
        fake = fake_frappe()
        fake.get_meta.side_effect = RuntimeError("SECRET_SAMPLE")
        result = run(fake)
        self.assertEqual(
            result["reason"], "METADATA_UNAVAILABLE"
        )
        self.assertNotIn("SECRET_SAMPLE", str(result))


if __name__ == "__main__":
    unittest.main(verbosity=2)
