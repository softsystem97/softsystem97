"""Offline safety tests for the ACTUAL Stripe accounting function.

No frappe, ERPNext, network, credentials, client data or writes required.
Extracts only the real production function AST and supplies synthetic stubs.
This is NOT an ERPNext integration test and cannot approve LIVE release.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "softsystem97" / "integrations" / "stripe" / "payment_sync.py"


class SyntheticValidationError(Exception):
    pass


def load_real_function(stubs):
    """Compile exactly one function from the actual production file."""
    tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"), filename=str(SOURCE))
    found = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name == "process_successful_payment"]
    if len(found) != 1:
        raise AssertionError("process_successful_payment introuvable ou ambigu")
    # Avoid importing the Frappe environment while exercising this actual code.
    module = ast.Module(body=found, type_ignores=[])
    ast.fix_missing_locations(module)
    scope = {"Any": Any, **stubs}
    exec(compile(module, str(SOURCE), "exec"), scope)
    return scope["process_successful_payment"]


class AccountingWithoutFrappeTests(unittest.TestCase):
    def setUp(self):
        self.database = Mock()
        self.database.get_value.return_value = 100
        self.frappe = SimpleNamespace(
            db=self.database,
            ValidationError=SyntheticValidationError,
            throw=self._raise,
            utils=SimpleNamespace(escape_html=lambda value: value),
        )
        self.entry = Mock(return_value=None)
        self.invoice_update = Mock()
        self.notify = Mock()
        self.comment = Mock()
        self.stubs = dict(
            frappe=self.frappe,
            flt=lambda value: float(value or 0),
            verify_amount_currency=Mock(return_value=(True, "")),
            is_confirmed_payment=lambda obj, kind: (
                kind == "checkout.session.completed" and obj.get("payment_status") == "paid"),
            generate_receipt_ref=lambda: "SYNTHETIC-RECEIPT",
            create_payment_entry_for_invoice=self.entry,
            update_invoice_stripe_fields=self.invoice_update,
            add_invoice_comment=self.comment,
            get_portal_user_for_customer=lambda customer: "SYNTHETIC-USER",
            create_client_notification=self.notify,
            now_datetime=lambda: "2026-10-29 00:00:00",
        )
        self.process = load_real_function(self.stubs)
        self.context = dict(
            object={"object": "checkout.session", "id": "cs_synthetic",
                    "payment_status": "paid"},
            event_type="checkout.session.completed",
            invoice="INV-SYNTHETIC", amount=100.0, currency="EUR",
            customer="CUSTOMER-SYNTHETIC",
        )

    @staticmethod
    def _raise(message, exc):
        raise exc(message)

    def test_missing_payment_entry_blocks_paid_and_notification(self):
        with self.assertRaises(SyntheticValidationError):
            self.process(self.context)
        self.invoice_update.assert_not_called()
        self.comment.assert_not_called()
        self.notify.assert_not_called()

    def test_successful_entry_allows_paid_recording(self):
        self.entry.return_value = "PE-SYNTHETIC"
        result = self.process(self.context)
        self.assertEqual(result["payment_entry"], "PE-SYNTHETIC")
        self.assertEqual(self.invoice_update.call_args.kwargs["payment_status"], "paid")
        self.notify.assert_called_once()

    def test_existing_settled_invoice_does_not_create_duplicate(self):
        self.database.get_value.return_value = 0
        result = self.process(self.context)
        self.assertTrue(result["skipped"])
        self.entry.assert_not_called()
        self.invoice_update.assert_not_called()
        self.notify.assert_not_called()

    def test_amount_validation_failure_never_posted(self):
        self.stubs["verify_amount_currency"].return_value = (False, "private")
        # Scope refers to the original Mock instance.
        with self.assertRaises(SyntheticValidationError):
            self.process(self.context)
        self.entry.assert_not_called()
        self.invoice_update.assert_not_called()
        self.notify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
