"""Native Frappe event ledger/concurrency, synthetic signatures, mocked billing.

No external Stripe call, real invoice, credentials or commercial data are used.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import hmac
import json
import threading
import time
import traceback
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import frappe
from softsystem97.integrations.stripe import webhook


class TestStripeLedger(unittest.TestCase):
    secret = 'ss97-ledger-synthetic-only'

    def setUp(self):
        if not frappe.conf.allow_tests or not frappe.local.site.startswith(('audit.', 'test_')):
            raise RuntimeError('Disposable site required')
        frappe.set_user('Administrator')
        self.response = patch.object(frappe.local, 'response', frappe._dict(), create=True)
        self.response.start()
        self.event_id = 'evt_synthetic_' + frappe.generate_hash(length=16)
        self.body = json.dumps(dict(id=self.event_id, type='checkout.session.completed',
            livemode=False, data={'object': {}})).encode()
        timestamp = int(time.time())
        digest = hmac.new(self.secret.encode(), str(timestamp).encode() + b'.' + self.body,
                          hashlib.sha256).hexdigest()
        self.request = SimpleNamespace(data=self.body,
            headers={'Stripe-Signature': f't={timestamp},v1={digest}'})

    def tearDown(self):
        frappe.db.rollback()
        frappe.set_user('Administrator')
        for name in frappe.get_all('SS97 Stripe Event', filters={'stripe_event_id': self.event_id}, pluck='name'):
            frappe.delete_doc('SS97 Stripe Event', name)
        frappe.db.commit()
        self.response.stop()

    def pending(self):
        doc = frappe.get_doc(dict(doctype='SS97 Stripe Event', stripe_event_id=self.event_id,
            event_type='checkout.session.completed', status='Pending', livemode=0)).insert()
        frappe.db.commit()
        return doc

    def test_signed_native_replay_dispatches_once(self):
        with patch.object(frappe.local, 'request', self.request, create=True), \
                patch.object(webhook, 'resolve_webhook_secret', return_value=self.secret), \
                patch.object(webhook, 'dispatch_stripe_event', return_value={'synthetic': True}) as dispatch:
            first = webhook._handle_stripe_webhook()
            second = webhook._handle_stripe_webhook()
        self.assertTrue(first['ok'])
        self.assertTrue(second['duplicate'])
        dispatch.assert_called_once()
        self.assertEqual(frappe.db.count('SS97 Stripe Event', {'stripe_event_id': self.event_id}), 1)
        self.assertEqual(frappe.db.get_value('SS97 Stripe Event', {'stripe_event_id': self.event_id}, 'status'), 'Success')

    def test_both_endpoints_expose_retry_conflict_without_commit(self):
        for endpoint in [webhook.stripe_webhook, webhook.webhook]:
            with self.subTest(endpoint=endpoint.__name__), \
                    patch.object(webhook, '_handle_stripe_webhook',
                        side_effect=frappe.QueryDeadlockError('synthetic conflict')), \
                    patch.object(frappe.db, 'commit') as commit:
                with self.assertRaises(webhook.StripeRetryConflict) as error:
                    endpoint()
                self.assertEqual(error.exception.http_status_code, 409)
                commit.assert_not_called()

    def test_concurrent_native_deliveries_dispatch_once(self):
        site, sites_path = frappe.local.site, frappe.local.sites_path
        barrier = threading.Barrier(2)
        count = []
        lock = threading.Lock()

        def dispatch(event):
            with lock:
                count.append(event['id'])
            time.sleep(0.15)  # Let the competing native connection reach the row lock.
            return {'synthetic': True}

        def deliver():
            frappe.init(site=site, sites_path=sites_path)
            frappe.connect()
            frappe.in_test = True
            frappe.flags.in_test = True
            frappe.set_user('Guest')
            frappe.local.request = self.request
            frappe.local.response = frappe._dict()
            try:
                barrier.wait(timeout=10)
                for attempt in range(4):
                    try:
                        result = webhook._handle_stripe_webhook()
                        frappe.db.commit()
                        return result
                    except (frappe.QueryDeadlockError, frappe.QueryTimeoutError,
                            frappe.DuplicateEntryError, frappe.UniqueValidationError):
                        frappe.db.rollback()  # A failed HTTP delivery is retried by Stripe.
                raise AssertionError('Native deliveries failed to converge')
            finally:
                frappe.db.rollback()
                frappe.destroy()

        with patch.object(webhook, 'resolve_webhook_secret', return_value=self.secret), \
                patch.object(webhook, 'dispatch_stripe_event', side_effect=dispatch):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: deliver(), range(2)))
        frappe.db.rollback()
        self.assertEqual(count, [self.event_id])
        self.assertEqual(sum(bool(r.get('duplicate')) for r in results), 1)
        self.assertEqual(frappe.db.count('SS97 Stripe Event', {'stripe_event_id': self.event_id}), 1)

    def test_claim_uses_current_read_after_snapshot_was_established(self):
        doc = self.pending()
        self.assertEqual(frappe.db.get_value('SS97 Stripe Event', doc.name, 'status'), 'Pending')
        site, sites_path = frappe.local.site, frappe.local.sites_path

        def complete():
            frappe.init(site=site, sites_path=sites_path)
            frappe.connect()
            try:
                frappe.db.set_value('SS97 Stripe Event', doc.name, 'status', 'Success')
                frappe.db.commit()
            finally:
                frappe.destroy()

        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(complete).result(timeout=10)
        try:
            row = webhook._lock_event(self.event_id, 'checkout.session.completed', False)
        except frappe.QueryDeadlockError:
            # MariaDB snapshot isolation can reject a stale locking read (1020).
            # A fresh request must retry after full rollback, without dispatch.
            frappe.db.rollback()
            row = webhook._lock_event(self.event_id, 'checkout.session.completed', False)
        self.assertEqual(row.status, 'Success')

    def test_upstream_error_text_is_not_logged_or_returned(self):
        marker = 'synthetic-private-upstream-value'
        with patch.object(frappe.local, 'request', self.request, create=True), \
                patch.object(webhook, 'resolve_webhook_secret', return_value=self.secret), \
                patch.object(webhook, 'dispatch_stripe_event', side_effect=RuntimeError(marker)), \
                patch.object(frappe, 'log_error') as log:
            with self.assertRaises(frappe.PermissionError) as error:
                webhook._handle_stripe_webhook()
            self.assertNotIn(marker, str(error.exception))
            self.assertNotIn(marker, ''.join(traceback.format_exception(error.exception)))
            self.assertNotIn(marker, str(log.call_args_list))
        row = frappe.db.get_value('SS97 Stripe Event', {'stripe_event_id': self.event_id},
                                 ['status', 'error'], as_dict=True)
        self.assertEqual(row.status, 'Failed')
        self.assertEqual(row.error, 'RuntimeError')

    def test_failed_old_delivery_does_not_overwrite_concurrent_success(self):
        self.pending()
        original = webhook._lock_event
        calls = []

        def claim(*args):
            calls.append(True)
            if len(calls) == 2:  # Simulate another delivery's committed success after rollback.
                frappe.db.set_value('SS97 Stripe Event', {'stripe_event_id': self.event_id}, 'status', 'Success')
                frappe.db.commit()
            return original(*args)

        with patch.object(frappe.local, 'request', self.request, create=True), \
                patch.object(webhook, 'resolve_webhook_secret', return_value=self.secret), \
                patch.object(webhook, '_lock_event', side_effect=claim), \
                patch.object(webhook, 'dispatch_stripe_event', side_effect=RuntimeError('synthetic')), \
                patch.object(frappe, 'log_error'):
            with self.assertRaises(frappe.PermissionError):
                webhook._handle_stripe_webhook()
        self.assertEqual(frappe.db.get_value('SS97 Stripe Event',
                         {'stripe_event_id': self.event_id}, 'status'), 'Success')
