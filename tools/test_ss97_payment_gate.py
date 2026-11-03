"""Offline synthetic tests for inactive Stripe payment evidence gate."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "softsystem97" / "integrations" / "ticket_bridge" / "payment_gate.py"
spec = importlib.util.spec_from_file_location("ss97_payment_gate", path)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class PaymentGateTests(unittest.TestCase):
    def setUp(self):
        self.invoice = dict(name="INV-TEST", grand_total=100, outstanding_amount=0, docstatus=1,
                            currency="EUR", customer="SYNTHETIC", ss97_payment_status="paid")
        self.event = dict(status="Success", livemode=1, event_type="checkout.session.completed",
                          currency="EUR", result='{"invoice":"INV-TEST","payment_entry":"PE-TEST"}')
        self.entry = dict(docstatus=1, payment_type="Receive", party_type="Customer", party="SYNTHETIC")
        self.ref = dict(reference_doctype="Sales Invoice", reference_name="INV-TEST", allocated_amount=100)

    def evaluate(self, invoice=None, events=None, entries=None, refs=None):
        return gate.invoice_is_fully_stripe_paid(
            self.invoice if invoice is None else invoice,
            [self.event] if events is None else events,
            {"PE-TEST": self.entry} if entries is None else entries,
            {"PE-TEST": [self.ref]} if refs is None else refs)

    def test_positive_synthetic_case(self):
        self.assertTrue(self.evaluate())

    def test_no_stripe_event(self):
        self.assertFalse(self.evaluate(events=[]))

    def test_testmode_rejected(self):
        self.assertFalse(self.evaluate(events=[dict(self.event, livemode=False)]))

    def test_missing_payment_entry(self):
        self.assertFalse(self.evaluate(entries={}))

    def test_draft_entry(self):
        self.assertFalse(self.evaluate(entries={"PE-TEST":dict(self.entry, docstatus=0)}))

    def test_wrong_customer(self):
        self.assertFalse(self.evaluate(entries={"PE-TEST":dict(self.entry, party="OTHER")}))

    def test_unpaid_invoice(self):
        self.assertFalse(self.evaluate(invoice=dict(self.invoice, outstanding_amount=90)))

    def test_wrong_invoice_allocation(self):
        self.assertFalse(self.evaluate(refs={"PE-TEST":[dict(self.ref, reference_name="OTHER")]}))

    def test_partial_payment(self):
        self.assertFalse(self.evaluate(refs={"PE-TEST":[dict(self.ref, allocated_amount=5)]}))

    def test_wrong_currency(self):
        self.assertFalse(self.evaluate(events=[dict(self.event, currency="USD")]))

    def test_duplicate_event_not_double_counted(self):
        self.assertFalse(self.evaluate(events=[self.event, self.event],
                          refs={"PE-TEST":[dict(self.ref, allocated_amount=60)]}))

    def test_unrecognized_event(self):
        self.assertFalse(self.evaluate(events=[dict(self.event, event_type="invoice.payment_failed")]))




class IssueInvoiceLinkTests(unittest.TestCase):
    def run_gate(self, invoices, issue=None):
        import sys
        import types
        from unittest.mock import patch
        frappe = types.ModuleType("frappe")
        frappe.get_meta = lambda doc: types.SimpleNamespace(
            has_field=lambda field: field in (
                ("customer",) if doc == "Issue" else
                ("ss97_linked_issue", "ss97_payment_status")
            )
        )
        frappe.db = types.SimpleNamespace(
            get_value=lambda doctype, name, fields, as_dict=False:
                issue if doctype == "Issue" else None,
        )
        frappe.get_all = lambda doctype, **kwargs: invoices if doctype == "Sales Invoice" else []
        with patch.dict(sys.modules, {"frappe": frappe}):
            return gate.issue_has_verified_stripe_payment("ISSUE-TEST")

    def test_missing_invoice_link_denied(self):
        self.assertFalse(self.run_gate([], {"name": "ISSUE-TEST", "customer": "SYNTHETIC"}))

    def test_duplicate_invoice_link_denied(self):
        rows = [{"name": "INV-A", "ss97_linked_issue": "ISSUE-TEST", "customer": "SYNTHETIC"},
                {"name": "INV-B", "ss97_linked_issue": "ISSUE-TEST", "customer": "SYNTHETIC"}]
        self.assertFalse(self.run_gate(rows, {"name": "ISSUE-TEST", "customer": "SYNTHETIC"}))

    def test_wrong_customer_invoice_denied(self):
        row = {"name": "INV-A", "ss97_linked_issue": "ISSUE-TEST", "customer": "OTHER"}
        self.assertFalse(self.run_gate([row], {"name": "ISSUE-TEST", "customer": "SYNTHETIC"}))

    def test_wrong_ticket_link_denied(self):
        row = {"name": "INV-A", "ss97_linked_issue": "ISSUE-OTHER", "customer": "SYNTHETIC"}
        self.assertFalse(self.run_gate([row], {"name": "ISSUE-TEST", "customer": "SYNTHETIC"}))


class OptInGuardTests(unittest.TestCase):
    def setUp(self):
        import sys
        import types
        from unittest.mock import patch
        self.sys = sys
        self.types = types
        self.patch = patch

    def make_frappe(self, config):
        module = self.types.ModuleType("frappe")
        module.conf = {"ss97_ticket_bridge": config}
        module.PermissionError = type("PermissionError", (Exception,), {})
        def fail(message, exc):
            raise exc(message)
        module.throw = fail
        return module

    def test_flag_off_does_not_authorize(self):
        fake = self.make_frappe({"enforce_paid_interventions": False})
        with self.patch.dict(self.sys.modules, {"frappe": fake}):
            self.assertFalse(gate.require_paid_intervention("ISSUE-1", "assign"))

    def test_verified_payment_flag_on(self):
        fake = self.make_frappe({"enforce_paid_interventions": True})
        with self.patch.dict(self.sys.modules, {"frappe": fake}):
            with self.patch.object(gate, "issue_has_verified_stripe_payment", return_value=True):
                self.assertTrue(gate.require_paid_intervention("ISSUE-1", "intervention"))

    def test_unpaid_flag_on_denied(self):
        fake = self.make_frappe({"enforce_paid_interventions": True})
        with self.patch.dict(self.sys.modules, {"frappe": fake}):
            with self.patch.object(gate, "issue_has_verified_stripe_payment", return_value=False):
                with self.assertRaises(fake.PermissionError):
                    gate.require_paid_intervention("ISSUE-1", "status")

    def test_exception_during_proof_denied(self):
        fake = self.make_frappe({"enforce_paid_interventions": True})
        with self.patch.dict(self.sys.modules, {"frappe": fake}):
            with self.patch.object(gate, "issue_has_verified_stripe_payment", side_effect=RuntimeError("private")):
                with self.assertRaises(fake.PermissionError):
                    gate.require_paid_intervention("ISSUE-1", "assign")

    def test_unknown_operation_denied(self):
        fake = self.make_frappe({})
        with self.patch.dict(self.sys.modules, {"frappe": fake}):
            with self.assertRaises(fake.PermissionError):
                gate.require_paid_intervention("ISSUE-1", "delete")

if __name__ == "__main__":
    unittest.main()
