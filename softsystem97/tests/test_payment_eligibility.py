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
    def test_checkout_complete_does_not_mean_paid(self):
        for payment_status in ['unpaid', 'failed', 'canceled', '', None]:
            with self.subTest(payment_status=payment_status):
                self.assertFalse(payment_sync.is_confirmed_payment(
                    {'status': 'complete', 'payment_status': payment_status},
                    'checkout.session.completed'))
        for payment_status in ['paid', 'no_payment_required']:
            self.assertTrue(payment_sync.is_confirmed_payment(
                {'status': 'complete', 'payment_status': payment_status}, 'checkout.session.completed'))
        self.assertFalse(payment_sync.is_confirmed_payment(
            {'status': 'open', 'amount_paid': 25}, 'invoice.paid'))

    def test_failure_cancellation_refund_and_pending_never_dispatch_as_paid(self):
        cases = [('checkout.session.completed', {'status': 'complete', 'payment_status': 'unpaid'}, 'skip'),
                 ('checkout.session.completed', {'status': 'complete', 'payment_status': 'canceled'}, 'failed'),
                 ('payment_intent.payment_failed', {'status': 'requires_payment_method'}, 'failed'),
                 ('payment_intent.canceled', {'status': 'canceled'}, 'skip'),
                 ('checkout.session.expired', {'status': 'expired', 'payment_status': 'unpaid'}, 'skip'),
                 ('invoice.payment_failed', {'status': 'open'}, 'failed'),
                 ('charge.refunded', {'refunded': True}, 'refund')]
        for kind, obj, expected in cases:
            ctx = dict(object=obj, event_type=kind)
            with self.subTest(kind=kind, obj=obj), \
                    patch.object(payment_sync, 'extract_event_context', return_value=ctx), \
                    patch.object(payment_sync, 'process_successful_payment') as paid, \
                    patch.object(payment_sync, 'process_failed_payment', return_value={'failed': True}) as failed, \
                    patch.object(payment_sync, 'process_refund', return_value={'refund': True}) as refund:
                result = payment_sync.dispatch_stripe_event({'type': kind})
                paid.assert_not_called()
                self.assertEqual(failed.call_count, int(expected == 'failed'))
                self.assertEqual(refund.call_count, int(expected == 'refund'))
                if expected == 'skip':
                    self.assertTrue(result['skipped'])

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
