"""Native ERPNext posting on an explicitly disposable site; no external charge.

These tests use synthetic HMAC deliveries, real SQL/GL/Payment Entry operations,
and real portal notifications. An actual Stripe delivery to staging is separate.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import hmac
import json
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from softsystem97.integrations.stripe import webhook
from softsystem97.integrations.ticket_bridge.payment_gate import issue_has_verified_stripe_payment


class TestStripeAccounting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (not frappe.conf.allow_tests or frappe.conf.get('ss97_stripe_test_site') is not True
                or not frappe.local.site.startswith(('audit.', 'test_'))):
            raise RuntimeError('Disposable test site required')
        frappe.set_user('Administrator')
        cls.company = 'SS97 Stripe Audit'
        if not frappe.db.exists('Company', cls.company):
            frappe.get_doc(dict(doctype='Company', company_name=cls.company, abbr='S97',
                default_currency='EUR', country='France', create_chart_of_accounts_based_on='Standard Template',
                chart_of_accounts='Standard', enable_perpetual_inventory=0)).insert()
        year = str(frappe.utils.getdate().year)
        if not frappe.db.exists('Fiscal Year', year):
            frappe.get_doc(dict(doctype='Fiscal Year', year=year, year_start_date=year+'-01-01',
                year_end_date=year+'-12-31')).insert()
        cls.bank = frappe.db.get_value('Account', {'company':cls.company,'account_type':'Bank','is_group':0},'name')
        if not cls.bank:
            parent = frappe.db.get_value('Account', {'company':cls.company,'root_type':'Asset','is_group':1},'name')
            cls.bank = frappe.get_doc(dict(doctype='Account', account_name='Stripe Clearing',
                parent_account=parent, company=cls.company, account_type='Bank', account_currency='EUR')).insert().name
        cls.receivable = frappe.db.get_value('Account', {'company':cls.company,'account_type':'Receivable','is_group':0},'name')
        cls.income = frappe.db.get_value('Account', {'company':cls.company,'root_type':'Income','is_group':0},'name')
        cls.cost_center = frappe.db.get_value('Cost Center', {'company':cls.company,'is_group':0},'name')
        cls.service = 'stripe-service@ss97.example.invalid'
        cls.client = 'stripe-client@ss97.example.invalid'
        for user, roles, kind in [(cls.service,['Accounts Manager'],'System User'),(cls.client,['Customer'],'Website User')]:
            if not frappe.db.exists('User',user):
                frappe.get_doc(dict(doctype='User',email=user,first_name='Stripe Audit',enabled=1,
                    user_type=kind,send_welcome_email=0,roles=[dict(role=x) for x in roles])).insert()
        cls.customer = 'SS97 Stripe Audit Customer'
        if not frappe.db.exists('Customer',cls.customer):
            frappe.get_doc(dict(doctype='Customer',customer_name=cls.customer,customer_type='Individual',
                customer_group=frappe.db.get_value('Customer Group',{'is_group':0},'name'),
                territory=frappe.db.get_value('Territory',{'is_group':0},'name'),
                ss97_stripe_customer_id='cus_ss97_audit',portal_users=[dict(user=cls.client)])).insert()
        if not frappe.db.exists('Price List','SS97 Audit Selling'):
            frappe.get_doc(dict(doctype='Price List',price_list_name='SS97 Audit Selling',currency='EUR',selling=1,enabled=1)).insert()
        cls.item = 'SS97 Stripe Audit Service'
        if not frappe.db.exists('Item',cls.item):
            frappe.get_doc(dict(doctype='Item',item_code=cls.item,item_name=cls.item,
                item_group=frappe.db.get_value('Item Group',{'is_group':0},'name'),is_stock_item=0,stock_uom='Nos')).insert()
        frappe.db.set_single_value('SS97 Stripe Config',{'service_user':cls.service,'clearing_account':cls.bank,'test_mode':1,'payments_live_enabled':0})
        frappe.db.commit()

    def setUp(self):
        frappe.set_user('Administrator')
        self.event_ids = []
        self.issue = frappe.get_doc(dict(doctype='Issue',subject='Stripe controlled audit',
            raised_by=self.client,customer=self.customer,status='Open')).insert()
        self.invoice = frappe.get_doc(dict(doctype='Sales Invoice',customer=self.customer,
            company=self.company,currency='EUR',conversion_rate=1,debit_to=self.receivable,
            selling_price_list='SS97 Audit Selling',price_list_currency='EUR',plc_conversion_rate=1,
            due_date=frappe.utils.today(),ss97_linked_issue=self.issue.name,ss97_stripe_mode='test',
            ss97_payment_status='pending',items=[dict(item_code=self.item,qty=1,rate=100,
                income_account=self.income,cost_center=self.cost_center)])).insert()
        self.invoice.submit()
        self.pi = 'pi_ss97_' + frappe.generate_hash(length=16)
        frappe.db.set_value('Sales Invoice',self.invoice.name,'ss97_stripe_payment_intent',self.pi)
        frappe.db.commit()
        self.secret = 'whsec_' + frappe.generate_hash(length=40)
        config=frappe.get_single('SS97 Stripe Config')
        config.test_webhook_secret=self.secret
        config.save()
        frappe.db.commit()

    def tearDown(self):
        frappe.db.rollback()
        frappe.set_user('Administrator')
        # The entire database is disposable; retain audit receipts/GL for inspection.

    def event(self, kind='payment_intent.succeeded', amount=10000, currency='eur'):
        event_id = 'evt_ss97_' + frappe.generate_hash(length=16)
        self.event_ids.append(event_id)
        obj = dict(object='payment_intent',id=self.pi,status='succeeded',customer='cus_ss97_audit',
            amount=amount,amount_received=amount,currency=currency,metadata={'invoice':self.invoice.name})
        if kind.startswith('checkout.'):
            obj.update(object='checkout.session',id='cs_ss97_'+frappe.generate_hash(length=16),
                payment_intent=self.pi,payment_status='paid',amount_total=amount)
        if kind == 'charge.refunded':
            obj.update(object='charge',id='ch_ss97_'+frappe.generate_hash(length=16),payment_intent=self.pi,
                amount=10000,amount_refunded=amount)
        return dict(id=event_id,type=kind,livemode=False,created=int(time.time()),data={'object':obj})

    def deliver(self, event):
        raw=json.dumps(event).encode()
        timestamp=int(time.time())
        signature=hmac.new(self.secret.encode(),str(timestamp).encode()+b'.'+raw,hashlib.sha256).hexdigest()
        request=SimpleNamespace(data=raw,headers={'Stripe-Signature':f't={timestamp},v1={signature}'})
        with patch.object(frappe.local,'request',request,create=True), \
             patch.object(frappe.local,'response',frappe._dict(),create=True):
            return webhook.stripe_webhook()

    def test_native_receipt_notification_gate_and_replay(self):
        self.assertFalse(issue_has_verified_stripe_payment(self.issue.name))
        event=self.event()
        frappe.set_user('Guest')
        result=self.deliver(event)
        self.assertEqual(frappe.session.user,'Guest')
        pe=frappe.get_doc('Payment Entry',result['result']['payment_entry'])
        self.assertEqual(pe.docstatus,1)
        self.assertEqual(pe.party,self.customer)
        self.assertEqual(pe.paid_to,self.bank)
        self.assertEqual(pe.references[0].reference_name,self.invoice.name)
        self.assertEqual(pe.references[0].allocated_amount,100)
        self.assertEqual(frappe.db.get_value('Sales Invoice',self.invoice.name,'outstanding_amount'),0)
        self.assertTrue(frappe.db.exists('GL Entry',{'voucher_type':'Payment Entry','voucher_no':pe.name,'is_cancelled':0}))
        self.assertTrue(issue_has_verified_stripe_payment(self.issue.name))
        self.assertTrue(self.deliver(event)['duplicate'])
        self.deliver(self.event(kind='checkout.session.completed'))
        self.assertEqual(frappe.db.count('Payment Entry',{'ss97_stripe_transaction_id':'test:'+self.pi}),1)
        self.assertEqual(frappe.db.count('SS97 Client Notification',{'for_user':self.client,'reference_name':self.invoice.name}),1)

    def test_amount_currency_rejected_without_ledger_posting(self):
        for amount,currency in [(9999,'eur'),(10000,'usd')]:
            with self.assertRaises(frappe.PermissionError) as error:
                self.deliver(self.event(amount=amount,currency=currency))
            self.assertEqual(error.exception.http_status_code,500)
        self.assertEqual(frappe.db.count('Payment Entry',{'ss97_stripe_transaction_id':'test:'+self.pi}),0)
        self.assertFalse(issue_has_verified_stripe_payment(self.issue.name))

    def test_refund_and_late_failure_never_release_work(self):
        self.deliver(self.event())
        self.deliver(self.event(kind='payment_intent.payment_failed'))
        self.assertEqual(frappe.db.get_value('Sales Invoice',self.invoice.name,'ss97_payment_status'),'paid')
        result=self.deliver(self.event(kind='charge.refunded',amount=2500))
        self.assertTrue(result['result']['accounting_review_required'])
        self.assertFalse(issue_has_verified_stripe_payment(self.issue.name))
        self.assertEqual(frappe.db.count('Payment Entry',{'ss97_stripe_transaction_id':'test:'+self.pi}),1)

    def test_distinct_concurrent_events_post_once(self):
        site,sites_path=frappe.local.site,frappe.local.sites_path
        barrier=threading.Barrier(2)
        events=[self.event(),self.event(kind='checkout.session.completed')]
        def deliver(event):
            frappe.init(site=site,sites_path=sites_path)
            frappe.connect()
            frappe.set_user('Guest')
            frappe.flags.in_test=True
            try:
                barrier.wait(timeout=15)
                for _ in range(4):
                    try:return self.deliver(event)
                    except webhook.StripeRetryConflict:frappe.db.rollback()
                    except frappe.PermissionError as error:
                        if error.http_status_code != 500:raise
                        frappe.db.rollback()
                raise AssertionError('Concurrent deliveries did not converge')
            finally:
                frappe.db.rollback()
                frappe.destroy()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(deliver,events))
        frappe.db.rollback()
        self.assertTrue(all(result['ok'] for result in results))
        self.assertEqual(frappe.db.count('Payment Entry',{'ss97_stripe_transaction_id':'test:'+self.pi}),1)
        self.assertTrue(issue_has_verified_stripe_payment(self.issue.name))

    def test_real_http_signed_delivery_and_invalid_replay(self):
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        from werkzeug.serving import make_server
        from frappe.app import application
        config=frappe.get_single('SS97 Stripe Config')
        config.test_webhook_secret=self.secret
        config.save()
        frappe.db.commit()
        event=self.event()
        raw=json.dumps(event).encode()
        server=make_server('127.0.0.1',0,application,threaded=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        url=f'http://127.0.0.1:{server.server_port}/api/method/softsystem97.integrations.stripe.webhook.stripe_webhook'
        def send(timestamp,secret):
            digest=hmac.new(secret.encode(),str(timestamp).encode()+b'.'+raw,hashlib.sha256).hexdigest()
            request=Request(url,data=raw,method='POST',headers={'Host':frappe.local.site,
                'Content-Type':'application/json','Accept':'application/json',
                'Stripe-Signature':f't={timestamp},v1={digest}'})
            try:
                with urlopen(request,timeout=30) as response:return response.status,json.loads(response.read())
            except HTTPError as error:return error.code,json.loads(error.read())
        try:
            self.assertEqual(send(int(time.time()),'wrong-secret')[0],403)
            self.assertEqual(send(int(time.time())-301,self.secret)[0],403)
            code,result=send(int(time.time()),self.secret)
            self.assertEqual(code,200,result)
            self.assertTrue(result['message']['ok'])
            self.assertTrue(send(int(time.time()),self.secret)[1]['message']['duplicate'])
        finally:
            server.shutdown()
            thread.join(timeout=10)
        frappe.db.rollback()
        self.assertEqual(frappe.db.get_value('SS97 Stripe Event',{'stripe_event_id':event['id']},'status'),'Success')
        self.assertEqual(frappe.db.count('Payment Entry',{'ss97_stripe_transaction_id':'test:'+self.pi}),1)

    def test_native_issue_status_requires_posted_payment(self):
        doc=frappe.get_doc('Issue',self.issue.name)
        doc.status='Replied'
        with self.assertRaises(frappe.PermissionError): doc.save()
        frappe.db.rollback()
        self.assertEqual(frappe.db.get_value('Issue',self.issue.name,'status'),'Open')
        self.deliver(self.event())
        doc=frappe.get_doc('Issue',self.issue.name)
        doc.status='Replied'
        doc.save()
        self.assertEqual(frappe.db.get_value('Issue',self.issue.name,'status'),'Replied')

    def test_checkout_binds_invoice_and_separates_client_permissions(self):
        from softsystem97.integrations.stripe import checkout
        from unittest.mock import Mock
        client=Mock()
        client.v1.checkout.sessions.create.return_value=SimpleNamespace(
            id='cs_ss97_checkout_'+frappe.generate_hash(length=12),url='https://checkout.stripe.com/c/pay/test_fixture')
        old_host=frappe.conf.get('host_name')
        frappe.conf.host_name='https://test-stripe.example.invalid'
        try:
            frappe.set_user(self.service)
            with self.assertRaises(frappe.PermissionError):checkout.create_ticket_checkout(self.issue.name)
            frappe.set_user(self.client)
            with patch.object(checkout,'stripe_client',return_value=client):
                result=checkout.create_ticket_checkout(self.issue.name)
            payload=client.v1.checkout.sessions.create.call_args.args[0]
            self.assertEqual(payload['line_items'][0]['price_data']['unit_amount'],10000)
            self.assertEqual(payload['customer'],'cus_ss97_audit')
            self.assertEqual(payload['payment_intent_data']['metadata']['invoice'],self.invoice.name)
            self.assertNotIn('payment_method_types',payload)
            self.assertEqual(result['invoice'],self.invoice.name)
            self.assertEqual(frappe.db.get_value('Sales Invoice',self.invoice.name,'ss97_stripe_session_id'),result['session_id'])
        finally:
            frappe.set_user('Administrator')
            if old_host is None:frappe.conf.pop('host_name',None)
            else:frappe.conf.host_name=old_host

    def _legacy_confirmation(self, *, user=None, method='POST', ticket=None):
        from frappe.utils.safe_exec import safe_exec
        from softsystem97.integrations.stripe.runtime_install import CONFIRM_PAYMENT_SCRIPT
        frappe.set_user(user or self.client)
        request = SimpleNamespace(method=method, path='/api/method/ss97_ticket_confirm_payment')
        response = frappe._dict(http_status_code=200)
        arguments = frappe._dict(ticket=ticket or self.issue.name,
            session_id='cs_live_untrusted_browser_value', invoice='UNTRUSTED-INVOICE', amount=1)
        with patch.object(frappe.local,'request',request,create=True), \
             patch.object(frappe.local,'response',response,create=True), \
             patch.object(frappe.local,'form_dict',arguments,create=True):
            safe_exec(CONFIRM_PAYMENT_SCRIPT, script_filename='SS97 legacy confirmation regression')
            return response.message

    def test_legacy_redirect_cannot_forge_payment_but_real_posting_confirms(self):
        # Regression: the deployed old API accepted browser hints and db_set paid.
        before = frappe.db.count('Payment Entry')
        self.assertFalse(self._legacy_confirmation()['ok'])
        self.assertEqual(frappe.db.count('Payment Entry'), before)
        self.assertEqual(frappe.db.get_value('Sales Invoice',self.invoice.name,'outstanding_amount'),100)
        self.deliver(self.event())
        self.assertTrue(self._legacy_confirmation()['ok'])
        self.assertEqual(frappe.db.count('Payment Entry'), before + 1)

    def test_legacy_confirmation_requires_post_session_and_ticket_ownership(self):
        with self.assertRaises(frappe.PermissionError):
            self._legacy_confirmation(method='GET')
        with self.assertRaises(frappe.PermissionError):
            self._legacy_confirmation(user='Guest')
        frappe.set_user('Administrator')
        foreign = frappe.get_doc(dict(doctype='Issue',subject='Other owner',raised_by=self.service,
            customer=self.customer,status='Open')).insert()
        with self.assertRaises(frappe.PermissionError):
            self._legacy_confirmation(ticket=foreign.name)
