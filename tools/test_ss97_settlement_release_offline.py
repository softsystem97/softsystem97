"""Offline checks: beneficiary and invoice safeguards, never a real transfer."""

import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class SettlementReleaseTests(unittest.TestCase):
    def test_free_or_verified_tickets_only_reach_internal_finance_review(self):
        fake_frappe = types.ModuleType("frappe")
        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            module = importlib.import_module("softsystem97.technician_os.settlement_controls")
            try:
                self.assertTrue(module.internal_financial_review_allowed("NO_INVOICE"))
                self.assertTrue(module.internal_financial_review_allowed("VERIFIED_PAID"))
                for state in ("UNVERIFIED", "UNAVAILABLE", "", None):
                    self.assertFalse(module.internal_financial_review_allowed(state))
                self.assertTrue(module.amounts_match_eur("100", "100.00"))
                self.assertFalse(module.amounts_match_eur("100.00", "101.00"))
                self.assertFalse(module.amounts_match_eur("invalid", "100.00"))
            finally:
                sys.modules.pop("softsystem97.technician_os.settlement_controls", None)

    def test_linked_invoice_requires_stripe_paid_proof_and_same_customer(self):
        fake_frappe = types.ModuleType("frappe")
        fake_frappe.get_meta = lambda _doctype: types.SimpleNamespace(has_field=lambda _field: True)
        invoices = []
        fake_frappe.get_all = lambda *_args, **_kwargs: invoices
        policy = types.ModuleType("softsystem97.integrations.ticket_bridge.payment_gate")
        policy.issue_has_verified_stripe_payment = lambda _issue: False
        with patch.dict(sys.modules, {"frappe": fake_frappe,
                                      "softsystem97.integrations.ticket_bridge.payment_gate": policy}):
            module = importlib.import_module("softsystem97.technician_os.settlement_controls")
            try:
                mission = types.SimpleNamespace(ticket_name="ISS-001", customer="CUST-001")
                self.assertEqual(module.ticket_payment_evidence(mission), "NO_INVOICE")
                invoices.append(types.SimpleNamespace(name="INV-001", customer="CUST-002"))
                self.assertEqual(module.ticket_payment_evidence(mission), "UNVERIFIED")
                invoices[0].customer = "CUST-001"
                self.assertEqual(module.ticket_payment_evidence(mission), "UNVERIFIED")
                policy.issue_has_verified_stripe_payment = lambda _issue: True
                self.assertEqual(module.ticket_payment_evidence(mission), "VERIFIED_PAID")
                invoices.append(types.SimpleNamespace(name="INV-002", customer="CUST-001"))
                self.assertEqual(module.ticket_payment_evidence(mission), "UNVERIFIED")
                fake_frappe.get_meta = lambda _doctype: types.SimpleNamespace(has_field=lambda _field: False)
                self.assertEqual(module.ticket_payment_evidence(mission), "UNAVAILABLE")
            finally:
                sys.modules.pop("softsystem97.technician_os.settlement_controls", None)

    def test_financial_review_rechecks_proof_and_never_moves_funds(self):
        source = (ROOT / "softsystem97/technician_os/api.py").read_text(encoding="utf-8")
        first = source.split("def prepare_settlement(mission_id):", 1)[1].split("@frappe.whitelist", 1)[0]
        second = source.split("def approve_settlement(settlement_id, evidence_reference):", 1)[1].split("@frappe.whitelist", 1)[0]
        self.assertIn("internal_financial_review_allowed(ticket_payment_evidence(mission))", first)
        self.assertIn("internal_financial_review_allowed(ticket_payment_evidence(mission))", second)
        self.assertIn("manager in {settlement.prepared_by, mission.technician, mission.created_by_user}", second)
        self.assertIn("def get_settlement_readiness(settlement_id):", source)
        self.assertIn('"ready_for_transfer": False', source)
        self.assertNotIn("transfers.create", source)
        self.assertNotIn("payouts.create", source)


if __name__ == "__main__":
    unittest.main()
