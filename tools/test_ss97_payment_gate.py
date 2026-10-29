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


if __name__ == "__main__":
    unittest.main()
