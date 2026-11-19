"""No-network regression tests for opt-in, recipient-bound Remote Assist mail."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


SOURCE = Path(__file__).resolve().parents[1] / "softsystem97/remote/invitation.py"


def load(fake):
    with patch.dict(sys.modules, {"frappe": fake}):
        spec = importlib.util.spec_from_file_location("ss97_invitation_lab", SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def facade(*, enabled=True, outgoing=True, client=True, url="https://lab.example.invalid/ss97-remote-assist"):
    fake = types.ModuleType("frappe")
    fake.PermissionError = PermissionError
    fake.throw = Mock(side_effect=lambda message, *_: (_ for _ in ()).throw(PermissionError(message)))
    fake.conf = {"ss97_remote_assist": {"email_enabled": enabled, "email_account": "Lab outgoing"}}
    fake.utils = SimpleNamespace(get_url=Mock(return_value=url))
    fake.db = SimpleNamespace(get_value=Mock(side_effect=lambda doctype, name, *args, **kwargs: (
        SimpleNamespace(email_id="lab-sender@example.invalid", enable_outgoing=1) if outgoing else None
    ) if doctype == "Email Account" else (
        SimpleNamespace(email="client@example.invalid", enabled=1) if client else None
    )))
    fake.sendmail = Mock()
    return fake


class TestRemoteInvitation(unittest.TestCase):
    def setUp(self):
        self.ticket = SimpleNamespace(name="ISS-TEST-1", raised_by="client@example.invalid")

    def test_disabled_mode_never_reads_or_queues(self):
        fake = facade(enabled=False)
        self.assertFalse(load(fake).request_client_invitation(self.ticket))
        fake.db.get_value.assert_not_called()
        fake.sendmail.assert_not_called()

    def test_enabled_mode_sends_only_to_verified_ticket_owner(self):
        fake = facade()
        self.assertTrue(load(fake).request_client_invitation(self.ticket))
        email = fake.sendmail.call_args.kwargs
        self.assertEqual(email["recipients"], ["client@example.invalid"])
        self.assertEqual(email["sender"], "lab-sender@example.invalid")
        self.assertTrue(email["delayed"])
        self.assertEqual(email["reference_doctype"], "Issue")
        self.assertEqual(email["reference_name"], "ISS-TEST-1")
        self.assertIn("https://lab.example.invalid/ss97-remote-assist", email["message"])
        self.assertNotIn("join_code", email["message"])
        self.assertNotIn("device_binding", email["message"])
        self.assertNotIn("123456789", email["message"])
        fake.utils.get_url.assert_called_once_with("/ss97-remote-assist")

    def test_missing_sender_configuration_fails_closed(self):
        fake = facade(outgoing=False)
        with self.assertRaises(PermissionError):
            load(fake).request_client_invitation(self.ticket)
        fake.sendmail.assert_not_called()

    def test_disabled_or_missing_client_fails_closed(self):
        fake = facade(client=False)
        with self.assertRaises(PermissionError):
            load(fake).request_client_invitation(self.ticket)
        fake.sendmail.assert_not_called()

    def test_non_https_invite_url_is_not_sent(self):
        fake = facade(url="http://lab.example.invalid/ss97-remote-assist")
        with self.assertRaises(PermissionError):
            load(fake).request_client_invitation(self.ticket)
        fake.sendmail.assert_not_called()

    def test_ticket_reference_is_html_escaped(self):
        fake = facade()
        self.ticket.name = 'ISS-<script>alert(1)</script>'
        load(fake).request_client_invitation(self.ticket)
        self.assertNotIn("<script>", fake.sendmail.call_args.kwargs["message"])
        self.assertIn("&lt;script&gt;", fake.sendmail.call_args.kwargs["message"])

    def test_mail_queue_failure_cannot_be_silently_accepted(self):
        fake = facade()
        fake.sendmail.side_effect = RuntimeError("queue not available")
        with self.assertRaisesRegex(RuntimeError, "queue not available"):
            load(fake).request_client_invitation(self.ticket)


if __name__ == "__main__":
    unittest.main(verbosity=2)
