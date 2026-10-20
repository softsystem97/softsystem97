"""Focused payment validation with synthetic invoice context; no Stripe network."""
import unittest
from unittest.mock import patch
import hashlib
import hmac
import json
from types import SimpleNamespace

import frappe
from softsystem97.integrations.stripe import payment_sync, webhook


class TestPaymentEligibility(unittest.TestCase):
    def test_zero_payment_or_missing_currency_cannot_validate_nonzero_invoice(self):
        invoice = frappe._dict(grand_total=100, outstanding_amount=100, currency='USD')
        with patch.object(frappe.db, 'get_value', return_value=invoice):
            for amount, currency in [(0, 'USD'), (None, 'USD'), (100, None), (100, ''),
                                     (float('nan'), 'USD'), (float('inf'), 'USD'), ('invalid', 'USD')]:
                with self.subTest(amount=amount, currency=currency):
                    self.assertFalse(payment_sync.verify_amount_currency('SYNTHETIC', amount, currency)[0])

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


class TestStripeWebhookAuthentication(unittest.TestCase):
    # Fixed synthetic test material, never site credentials or Stripe network.
    secret = 'ss97-synthetic-test-only'
    timestamp = 1700000000
    body = json.dumps(dict(id='evt_synthetic_duplicate', type='checkout.session.completed',
                           livemode=False, data={'object': {}})).encode()

    def signature(self, timestamp):
        digest = hmac.new(self.secret.encode(), str(timestamp).encode() + b'.' + self.body,
                          hashlib.sha256).hexdigest()
        return f't={timestamp},v1={digest}'

    def test_signature_time_window_rejects_future_and_expired_requests(self):
        with patch.object(payment_sync.time, 'time', return_value=self.timestamp):
            for offset in [-301, 301, 86400]:
                with self.subTest(offset=offset):
                    self.assertFalse(payment_sync.verify_stripe_signature(
                        self.body, self.signature(self.timestamp + offset), self.secret))
            for offset in [-299, 0, 299]:
                with self.subTest(offset=offset):
                    self.assertTrue(payment_sync.verify_stripe_signature(
                        self.body, self.signature(self.timestamp + offset), self.secret))

    def test_unsigned_duplicate_rejected_before_event_lookup(self):
        request = SimpleNamespace(data=self.body, headers={})
        with patch.object(frappe.local, 'request', request, create=True), \
                patch.object(frappe.local, 'response', frappe._dict(), create=True), \
                patch.object(webhook, 'resolve_webhook_secret', return_value=self.secret), \
                patch.object(webhook, 'event_already_processed', return_value=True) as lookup, \
                patch.object(webhook, 'dispatch_stripe_event') as dispatch, \
                patch.object(frappe.db, 'commit') as commit:
            with self.assertRaises(frappe.PermissionError):
                webhook._handle_stripe_webhook()
            self.assertEqual(frappe.local.response.http_status_code, 403)
            lookup.assert_not_called()
            dispatch.assert_not_called()
            commit.assert_not_called()

    def test_signed_duplicate_acknowledged_without_dispatch_or_writes(self):
        request = SimpleNamespace(data=self.body,
            headers={'Stripe-Signature': self.signature(self.timestamp)})
        with patch.object(frappe.local, 'request', request, create=True), \
                patch.object(payment_sync.time, 'time', return_value=self.timestamp), \
                patch.object(webhook, 'resolve_webhook_secret', return_value=self.secret), \
                patch.object(webhook, 'event_already_processed', return_value=True) as lookup, \
                patch.object(webhook, 'dispatch_stripe_event') as dispatch, \
                patch.object(webhook, 'log_stripe_event') as log, \
                patch.object(frappe.db, 'commit') as commit:
            self.assertTrue(webhook._handle_stripe_webhook()['duplicate'])
            lookup.assert_called_once_with('evt_synthetic_duplicate')
            dispatch.assert_not_called()
            log.assert_not_called()
            commit.assert_not_called()
