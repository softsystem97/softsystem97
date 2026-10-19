"""Frappe v16 queue contracts; transport is mocked and no credentials are used."""
import smtplib
import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.email.doctype.email_queue.email_queue import EmailQueue, get_email_retry_limit
from frappe.email.queue import flush, get_queue


class TestMailQueue(unittest.TestCase):
    def setUp(self):
        if not frappe.conf.allow_tests or not frappe.local.site.startswith(('audit.', 'test_')):
            raise RuntimeError('Disposable audit/test site with allow_tests required')
        frappe.set_user('Administrator')
        self.names = []
        self.old_testing_email = frappe.flags.testing_email
        frappe.flags.testing_email = True

    def tearDown(self):
        frappe.flags.testing_email = self.old_testing_email
        frappe.db.rollback()
        for name in self.names:
            for log in frappe.get_all('Notification Log', filters={
                    'document_type': 'Email Queue', 'document_name': name}, pluck='name'):
                frappe.delete_doc('Notification Log', log)
            if frappe.db.exists('Email Queue', name):
                frappe.delete_doc('Email Queue', name)
        frappe.db.commit()

    def mail(self):
        doc = frappe.get_doc(dict(doctype='Email Queue', sender='sender@example.invalid',
            message='Subject: SS97 local retry test\nFrom: sender@example.invalid\nTo: <!--recipient-->\n\nSynthetic test',
            status='Not Sent', priority=1, recipients=[dict(recipient='recipient@example.invalid')])).insert()
        self.names.append(doc.name)
        frappe.db.commit()
        return doc

    def test_due_queue_respects_send_after_and_undo_window(self):
        ready, future, recent = self.mail(), self.mail(), self.mail()
        past = frappe.utils.add_to_date(None, seconds=-20)
        for doc in [ready, future]:
            frappe.db.set_value(doc.doctype, doc.name, 'creation', past, update_modified=False)
        frappe.db.set_value(future.doctype, future.name, 'send_after',
                            frappe.utils.add_to_date(None, hours=1), update_modified=False)
        names = {row.name for row in get_queue()}
        self.assertIn(ready.name, names)
        self.assertNotIn(future.name, names)
        self.assertNotIn(recent.name, names)

    def test_suspended_queue_does_not_send(self):
        self.mail()
        original = frappe.db.get_default
        def get_default(key):
            return 1 if key == 'suspend_email_queue' else original(key)
        with patch.object(frappe.db, 'get_default', side_effect=get_default), patch.object(EmailQueue, 'send') as send:
            flush()
            send.assert_not_called()

    def test_mail_condition_diagnostic_never_sends_or_reads_credentials(self):
        from softsystem97.diagnostics import queued_mail_conditions
        doc = self.mail()
        frappe.db.set_value(doc.doctype, doc.name, 'send_after',
                            frappe.utils.add_to_date(None, hours=1), update_modified=False)
        with patch.object(EmailQueue, 'send', side_effect=AssertionError('Must not send')):
            data = queued_mail_conditions(doc.name)
        self.assertFalse(data['send_after_due'])
        self.assertTrue(data['pending_send_status'])
        self.assertFalse(data['smtp_delivery_verified'])
        self.assertIsNone(data['explicit_outgoing_account'])
        self.assertNotIn('error', data['queue'])
        self.assertNotIn('message', data['queue'])
        self.assertNotIn('sender', data['queue'])
        self.assertEqual(frappe.db.get_value(doc.doctype, doc.name, 'status'), 'Not Sent')

    def transport(self):
        server = MagicMock()
        server.session.has_extn.return_value = False
        server.session.sendmail.side_effect = smtplib.SMTPRecipientsRefused(
            {'recipient@example.invalid': (450, b'local transient failure')})
        account = frappe._dict(service='SMTP', track_email_status=0, append_emails_to_sent_folder=0)
        return server, account

    def test_transient_failure_retries_then_sends_once(self):
        doc = self.mail()
        server, account = self.transport()
        with patch('frappe.are_emails_muted', return_value=False), patch.object(
                EmailQueue, 'get_email_account', return_value=account):
            with self.assertRaises(smtplib.SMTPRecipientsRefused):
                doc.send(smtp_server_instance=server)
            doc.reload()
            self.assertEqual(doc.status, 'Not Sent')
            self.assertEqual(doc.retry, 1)
            self.assertTrue(doc.error)
            server.session.sendmail.side_effect = None
            doc.send(smtp_server_instance=server)
            doc.reload()
            self.assertEqual(doc.status, 'Sent')
            self.assertEqual(doc.recipients[0].status, 'Sent')
            doc.send(smtp_server_instance=server)
            self.assertEqual(server.session.sendmail.call_count, 2)

    def test_exhausted_retry_limit_records_error(self):
        doc = self.mail()
        doc.retry = get_email_retry_limit()
        doc.save()
        server, account = self.transport()
        with patch('frappe.are_emails_muted', return_value=False), patch.object(
                EmailQueue, 'get_email_account', return_value=account):
            with self.assertRaises(smtplib.SMTPRecipientsRefused):
                doc.send(smtp_server_instance=server)
        doc.reload()
        self.assertEqual(doc.status, 'Error')
        self.assertTrue(doc.error)
