"""Focused payment validation with synthetic invoice context; no Stripe network."""
import unittest
from unittest.mock import patch

import frappe
from softsystem97.integrations.stripe import payment_sync


class TestPaymentEligibility(unittest.TestCase):
    def test_existing_amount_and_currency_checks_reject_mismatches(self):
        invoice = frappe._dict(grand_total=100, outstanding_amount=100, currency='USD')
        with patch.object(frappe.db, 'get_value', return_value=invoice):
            self.assertFalse(payment_sync.verify_amount_currency('SYNTHETIC', 10, 'USD')[0])
            self.assertFalse(payment_sync.verify_amount_currency('SYNTHETIC', 100, 'EUR')[0])
            self.assertTrue(payment_sync.verify_amount_currency('SYNTHETIC', 100, 'USD')[0])

    def test_failed_validation_cannot_mark_invoice_paid_or_notify(self):
        context = dict(object={'object': 'checkout.session', 'id': 'cs_synthetic',
                              'payment_status': 'paid'}, event_type='checkout.session.completed',
                       invoice='SYNTHETIC', amount=10, currency='USD', customer='SYNTHETIC-CUSTOMER')
        with patch.object(payment_sync, 'verify_amount_currency', return_value=(False, 'private values')), \
                patch.object(payment_sync, 'create_payment_entry_for_invoice') as entry, \
                patch.object(payment_sync, 'update_invoice_stripe_fields') as update, \
                patch.object(payment_sync, 'create_client_notification') as notification:
            with self.assertRaises(frappe.ValidationError) as error:
                payment_sync.process_successful_payment(context)
            self.assertNotIn('private values', str(error.exception))
            entry.assert_not_called()
            update.assert_not_called()
            notification.assert_not_called()
