"""Real handler code with an in-memory ledger; not ERPNext integration evidence."""
import hashlib
import hmac
import importlib
import json
import sys
import time
import types
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch


class Row(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__


class ValidationError(Exception):
    pass


class PermissionError(Exception):
    pass


def load_modules():
    fake = types.ModuleType("frappe")
    fake.utils = types.ModuleType("frappe.utils")
    fake.utils.cint = lambda value: int(value or 0)
    fake.utils.flt = lambda value: float(value or 0)
    fake.utils.now_datetime = Mock()
    fake.utils.escape_html = lambda value: value
    fake.utils.today = lambda: "2026-11-03"
    fake._ = lambda value: value
    fake._dict = Row
    fake.as_json = json.dumps
    fake.local = Row(site="test_stripe", response=Row())
    fake.session = Row(user="Guest")
    fake.conf = Row(STRIPE_MODE="test", PAYMENTS_LIVE_ENABLED=0, allow_tests=1, ss97_stripe_test_site=True)
    fake.db = Mock()
    fake.get_doc = Mock()
    fake.get_all = Mock(return_value=[])
    fake.get_meta = Mock()
    fake.get_single = Mock()
    fake.log_error = Mock()
    fake.ValidationError = ValidationError
    fake.PermissionError = PermissionError
    for kind in ("QueryDeadlockError", "QueryTimeoutError", "DuplicateEntryError", "UniqueValidationError"):
        setattr(fake, kind, type(kind, (Exception,), {}))
    fake.throw = lambda message, exc=ValidationError: (_ for _ in ()).throw(exc(message))
    fake.whitelist = lambda **options: lambda func: func
    fake.db.exists.return_value = False
    fake.set_user = lambda user: fake.session.update(user=user)
    fake.get_roles = Mock(return_value=["Accounts User"])
    names = ["softsystem97.integrations.stripe." + x for x in ("settings", "payment_sync", "webhook", "checkout")]
    with patch.dict(sys.modules, {"frappe": fake, "frappe.utils": fake.utils}):
        for name in names:
            sys.modules.pop(name, None)
        modules = [importlib.import_module(name) for name in names]
    return fake, modules


class StripeHardeningTests(unittest.TestCase):
    def setUp(self):
        self.frappe, (self.settings, self.sync, self.webhook, self.checkout) = load_modules()
        self.timestamp = int(time.time())
        self.secret = "whsec_" + "synthetic_fixture_only"
        self.event = dict(id="evt_local_test", type="payment_intent.succeeded", livemode=False,
            created=self.timestamp, data={"object": {"object": "payment_intent", "id": "pi_fixture",
            "status": "succeeded", "currency": "eur", "amount_received": 10000}})

    def signed_request(self, event=None, timestamp=None, secret=None):
        body = json.dumps(event or self.event).encode()
        timestamp = self.timestamp if timestamp is None else timestamp
        digest = hmac.new((secret or self.secret).encode(), str(timestamp).encode() + b"." + body, hashlib.sha256).hexdigest()
        return Row(data=body, headers={"Stripe-Signature": f"t={timestamp},v1={digest}"})

    def test_valid_signature_tampering_rotation_and_timestamp(self):
        request = self.signed_request()
        signature = request.headers["Stripe-Signature"]
        self.assertTrue(self.sync.verify_stripe_signature(request.data, signature, self.secret))
        self.assertFalse(self.sync.verify_stripe_signature(request.data + b" ", signature, self.secret))
        self.assertFalse(self.sync.verify_stripe_signature(request.data, signature, "wrong"))
        self.assertFalse(self.sync.verify_stripe_signature(request.data, 't='+'9'*400+',v1='+'0'*64, self.secret))
        for offset in (-301, 301):
            stale = self.signed_request(timestamp=self.timestamp + offset)
            self.assertFalse(self.sync.verify_stripe_signature(stale.data, stale.headers["Stripe-Signature"], self.secret))
        self.assertTrue(self.sync.verify_stripe_signature(request.data, signature + ",v1=" + "0" * 64, self.secret))
        self.assertFalse(self.sync.verify_stripe_signature(request.data, f"t={self.timestamp},v1=" + "é" * 64, self.secret))

    def test_wrong_secret_or_mode_cannot_dispatch(self):
        for change in ("signature", "live", "invalid_mode", "production_test"):
            with self.subTest(change=change):
                event = deepcopy(self.event)
                self.frappe.conf.update(STRIPE_MODE="test", ss97_stripe_test_site=True)
                if change == "live": event["livemode"] = True
                if change == "invalid_mode": self.frappe.conf.STRIPE_MODE = "typo"
                if change == "production_test": self.frappe.conf.ss97_stripe_test_site = False
                self.frappe.local.request = self.signed_request(event, secret="wrong" if change == "signature" else None)
                with patch.object(self.webhook, "resolve_webhook_secret", return_value=self.secret), \
                     patch.object(self.webhook, "event_already_processed", return_value=False), \
                     patch.object(self.webhook, "dispatch_stripe_event") as dispatch, \
                     patch.object(self.webhook, "log_stripe_event", return_value="LOG"):
                    with self.assertRaises(PermissionError): self.webhook.stripe_webhook()
                    dispatch.assert_not_called()

    def test_malformed_livemode_rejected(self):
        event = dict(self.event, livemode="false")
        self.frappe.local.request = self.signed_request(event)
        with self.assertRaises(PermissionError) as error:
            self.webhook.stripe_webhook()
        self.assertEqual(error.exception.http_status_code, 400)

    def test_signed_delivery_replay_and_failure_retry(self):
        self.frappe.local.request = self.signed_request()
        ledger = {}
        committed = {}
        def claim(event_id, kind, live):
            return Row(name="LOG", status=ledger.get(event_id, {}).get("status", "Pending"))
        def log(event_id, kind, **values):
            ledger[event_id] = values
            return "LOG"
        self.frappe.db.commit.side_effect = lambda: committed.update(deepcopy(ledger))
        def rollback():
            ledger.clear()
            ledger.update(deepcopy(committed))
        self.frappe.db.rollback.side_effect = rollback
        with patch.object(self.webhook, "resolve_webhook_secret", return_value=self.secret), \
             patch.object(self.webhook, "event_already_processed", side_effect=lambda event_id: ledger.get(event_id, {}).get("status") == "Success"), \
             patch.object(self.webhook, "_lock_event", side_effect=claim), \
             patch.object(self.webhook, "log_stripe_event", side_effect=log), \
             patch.object(self.sync, "extract_event_context", return_value={}), \
             patch.object(self.webhook, "dispatch_stripe_event", side_effect=[RuntimeError("private"), {"payment_entry":"PE"}]) as dispatch:
            with self.assertRaises(PermissionError) as error: self.webhook.stripe_webhook()
            self.assertEqual(error.exception.http_status_code, 500)
            self.assertEqual(ledger[self.event["id"]]["status"], "Failed")
            self.assertNotIn("private", str(ledger))
            self.assertTrue(self.webhook.stripe_webhook()["ok"])
            self.assertTrue(self.webhook.stripe_webhook()["duplicate"])
            self.assertEqual(dispatch.call_count, 2)
            self.assertEqual(ledger[self.event["id"]]["status"], "Success")

    def test_minor_units_and_exact_amounts(self):
        for currency, units, amount in [("EUR", 10001,100.01),("JPY",100,100),("KWD",1001,1.001),("ISK",10000,100)]:
            self.assertEqual(self.sync._amount_from_cents(units,currency),amount)
        self.frappe.db.get_value.return_value = Row(currency="EUR", outstanding_amount=100, grand_total=100)
        for amount,currency,expected in [(100,"EUR",True),(99.99,"EUR",False),(100.01,"EUR",False),(100,"USD",False),(float("nan"),"EUR",False),(0,"EUR",False)]:
            self.assertEqual(self.sync.verify_amount_currency("INV",amount,currency)[0],expected)

    def test_zero_received_does_not_fall_back_to_requested_amount(self):
        self.event["data"]["object"].update(amount_received=0, amount=10000)
        self.assertEqual(self.sync.extract_event_context(self.event)["amount"],0)

    def test_checkout_async_and_no_payment_required(self):
        for kind in ("checkout.session.completed","checkout.session.async_payment_succeeded"):
            self.assertTrue(self.sync.is_confirmed_payment({"payment_status":"paid"},kind))
            self.assertFalse(self.sync.is_confirmed_payment({"payment_status":"no_payment_required"},kind))
            self.assertFalse(self.sync.is_confirmed_payment({"payment_status":"unpaid"},kind))

    def test_credential_types_and_precedence(self):
        self.frappe.db.exists.return_value = True
        self.frappe.get_single.return_value.get_password.return_value = "database_secret"
        self.frappe.conf.STRIPE_TEST_WEBHOOK_SECRET = self.secret
        self.assertEqual(self.settings.password("test_webhook_secret","STRIPE_TEST_WEBHOOK_SECRET"),self.secret)
        self.frappe.conf.STRIPE_TEST_WEBHOOK_SECRET = "sk_test_" + "fixture"
        self.assertIsNone(self.sync.resolve_webhook_secret(False))
        with patch.dict(sys.modules, {"softsystem97.integrations.stripe.payment_sync": self.sync}), \
             patch.object(self.settings,"password",return_value=self.secret):
            with self.assertRaises(ValidationError): self.settings.stripe_client()

    def test_service_user_restored_after_failure(self):
        self.frappe.db.exists.return_value = True
        self.frappe.db.get_single_value.return_value = "stripe-service@example.invalid"
        self.frappe.db.get_value.return_value = 1
        with self.assertRaises(RuntimeError):
            with self.settings.accounting_user():
                self.assertEqual(self.frappe.session.user,"stripe-service@example.invalid")
                raise RuntimeError("fixture")
        self.assertEqual(self.frappe.session.user,"Guest")

    def test_stale_failure_does_not_revoke_paid_invoice(self):
        with patch.object(self.sync,"lock_invoice",return_value=Row(outstanding_amount=0,ss97_payment_status="paid")), \
             patch.object(self.sync,"update_invoice_stripe_fields") as update:
            self.assertTrue(self.sync.process_failed_payment({"object":{},"invoice":"INV"})["skipped"])
            update.assert_not_called()

    def test_refund_does_not_cancel_or_forge_accounting(self):
        context = dict(object={"amount_refunded":1000,"amount":10000},invoice="INV",currency="EUR",customer="C",livemode=False)
        with patch.object(self.sync,"lock_invoice",return_value=Row(currency="EUR")), patch.object(self.sync,"update_invoice_stripe_fields") as update, \
             patch.object(self.sync,"add_invoice_comment"), patch.object(self.sync,"get_portal_user_for_customer",return_value=None), \
             patch.object(self.sync,"create_payment_entry_for_invoice") as entry:
            self.assertTrue(self.sync.process_refund(context)["accounting_review_required"])
            self.assertEqual(update.call_args.kwargs["payment_status"],"refund_pending_review")
            entry.assert_not_called()

    def test_notification_failure_causes_retry(self):
        self.frappe.db.exists.return_value = True
        self.frappe.get_doc.return_value.insert.side_effect = RuntimeError("private")
        with self.assertRaises(ValidationError):
            self.sync.create_client_notification(for_user="client@example.invalid",subject="Paid",message="Receipt")

    def test_persisted_binding_conflicts_with_metadata_rejected(self):
        self.frappe.get_all.return_value = ['INV-A']
        obj = dict(object='payment_intent',id='pi_fixture',metadata={'invoice':'INV-B'})
        with self.assertRaises(ValidationError): self.sync.find_sales_invoice_from_stripe_object(obj)

    def test_metadata_fallback_requires_provider_customer_ownership(self):
        inv = Row(customer='ERP-C',ss97_stripe_mode='test')
        self.frappe.db.get_value.side_effect = [inv,'cus_expected']
        obj = dict(object='payment_intent',id='pi_fixture',customer='cus_other',metadata={'invoice':'INV-A'})
        with self.assertRaises(ValidationError): self.sync.find_sales_invoice_from_stripe_object(obj)

    def test_modern_invoice_payment_relation_and_credit_mixture(self):
        row = dict(status='paid',amount_paid=10000,currency='eur',payment={'type':'payment_intent','payment_intent':'pi_fixture'})
        obj = dict(object='invoice',status='paid',amount_paid=10000,currency='eur',payments={'data':[row]})
        self.assertEqual(self.sync.payment_intent_id(obj),'pi_fixture')
        obj['payments']['data'][0]['amount_paid']=5000
        self.assertIsNone(self.sync.payment_intent_id(obj))

    def test_deleted_subscription_cannot_be_resurrected(self):
        self.frappe.db.get_value.return_value = Row(ss97_stripe_subscription_id='sub_fixture',
            ss97_stripe_subscription_status='canceled',ss97_stripe_subscription_event_created=100)
        ctx = dict(object={'id':'sub_fixture','status':'active'},customer='C',event_type='customer.subscription.updated',event_created=99)
        self.assertTrue(self.sync.process_subscription_event(ctx)['skipped'])
        self.frappe.db.set_value.assert_not_called()

    def test_provider_failure_text_is_not_returned_or_chained(self):
        import traceback
        method=Mock(side_effect=RuntimeError('private-provider-fixture'))
        with self.assertRaises(ValidationError) as error:
            self.settings.stripe_call(method)
        self.assertNotIn('private-provider-fixture',''.join(traceback.format_exception(error.exception)))


if __name__ == "__main__":
    unittest.main()
