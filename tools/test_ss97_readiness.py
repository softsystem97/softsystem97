"""Exercise the private bridge preflight without a Frappe site."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

MODULE_NAME = "softsystem97.integrations.ticket_bridge.readiness"
SOURCE = (
    Path(__file__).resolve().parents[1]
    / "softsystem97/integrations/ticket_bridge/readiness.py"
)


def deny(message, error):
    raise error(message)


def fake_frappe(admin=True, enabled=True):
    fake = types.ModuleType("frappe")
    fake.whitelist = lambda methods: lambda func: func
    fake.PermissionError = PermissionError
    fake.throw = Mock(side_effect=deny)
    fake.session = types.SimpleNamespace(user="manager@example.test")
    fake.get_roles = Mock(side_effect={
        "manager@example.test": ["System Manager"] if admin else [],
        "writer@example.test": ["Support Team"],
    }.__getitem__)
    fake.conf = {
        "ss97_ticket_bridge": {
            "enabled": enabled,
            "technician_role": "SS97 Technicien N4",
            "profile_required": True,
            "writer_user": "writer@example.test",
            "compatibility_confirmed": True,
        },
        "ss97_tech_os": {"enabled": True},
        "ss97_technician_exams": {"enabled": True},
    }

    fake.db = Mock()
    fake.db.get_value.return_value = 1
    fake.db.exists.side_effect = lambda doctype, _: doctype != "Workflow"
    fake.db.count.return_value = 0

    issue = Mock()
    issue.get_field.side_effect = {
        "customer": types.SimpleNamespace(fieldtype="Link", options="Customer"),
        "status": types.SimpleNamespace(
            fieldtype="Select", options="Open\nReplied\nOn Hold\nResolved\nClosed"
        ),
    }.__getitem__
    bridge_event = Mock()
    bridge_event.has_field.return_value = True
    fake.get_meta = Mock(side_effect={
        "Issue": issue,
        "SS97 Ticket Bridge Event": bridge_event,
    }.__getitem__)
    fake.get_all = Mock(side_effect=lambda doctype, **kwargs: (
        [types.SimpleNamespace(name="writer@example.test")] if doctype == "User" else []
    ))
    return fake


def run(fake):
    with patch.dict(sys.modules, {"frappe": fake}):
        spec = importlib.util.spec_from_file_location(MODULE_NAME, SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.get_admin_bridge_preflight()


class TestReadiness(unittest.TestCase):

    def test_admin_required(self):
        fake = fake_frappe(admin=False)
        with self.assertRaises(PermissionError):
            run(fake)
        fake.db.exists.assert_not_called()

    def test_read_only_checks(self):
        fake = fake_frappe()
        result = run(fake)
        self.assertTrue(result["checks"]["issue_customer_link"])
        self.assertTrue(result["checks"]["issue_statuses_match"])
        self.assertTrue(result["checks"]["profile_adapter_confirmed"])
        self.assertTrue(result["activation_prerequisites_met"])
        self.assertNotIn("writer@example.test", str(result))
        fake.db.set_value.assert_not_called()
        fake.db.commit.assert_not_called()

    def test_disabled_bridge(self):
        result = run(fake_frappe(enabled=False))
        self.assertFalse(result["checks"]["bridge_enabled"])
        self.assertFalse(result["currently_enabled"])
        self.assertTrue(result["activation_prerequisites_met"])

    def test_private_errors_hidden(self):
        fake = fake_frappe()
        fake.db.count.side_effect = ValueError("private inventory detail")
        result = run(fake)
        self.assertFalse(result["checks"]["issue_scripts_inventory_complete"])
        self.assertFalse(result["activation_prerequisites_met"])
        self.assertNotIn("private inventory detail", str(result))


if __name__ == "__main__":
    unittest.main(verbosity=2)
