"""Integration regressions. Run only on a disposable site with allow_tests enabled."""
import unittest
from unittest.mock import patch

import frappe

from softsystem97.integrations.bridge import api
from softsystem97.portal import notifications


class TestAccess(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not frappe.conf.allow_tests or not frappe.local.site.startswith(('audit.', 'test_')):
            raise RuntimeError('Disposable audit/test site with allow_tests required')
        frappe.set_user('Administrator')
        cls.users = []
        for label, roles in [('client', ['Customer']), ('other', ['Customer']),
                             ('staff', ['System Manager']), ('unprivileged', [])]:
            email = f'ss97-audit-{label}@example.invalid'
            if frappe.db.exists('User', email):
                raise RuntimeError('Refusing to reuse an existing test user')
            doc = frappe.get_doc(dict(doctype='User', email=email, first_name=label,
                                      send_welcome_email=0, user_type='System User',
                                      roles=[dict(role=role) for role in roles]))
            doc.insert()
            cls.users.append(email)
        cls.client, cls.other, cls.staff, cls.unprivileged = cls.users
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user('Administrator')
        for user in reversed(cls.users):
            frappe.delete_doc('User', user)
        frappe.db.commit()

    def setUp(self):
        frappe.set_user('Administrator')
        self.records = []

    def tearDown(self):
        frappe.set_user('Administrator')
        frappe.db.rollback()
        for doctype, name in reversed(self.records):
            if frappe.db.exists(doctype, name):
                frappe.delete_doc(doctype, name)
        frappe.db.commit()

    def request(self):
        request_id = 'audit-' + frappe.generate_hash(length=12)
        api.create_request(action='audit', samAccountName='audit', displayName='Audit',
                           role='Audit', requestId=request_id)
        name = frappe.db.get_value(api.DOCTYPE, {'request_id': request_id}, 'name')
        self.records.append((api.DOCTYPE, name))
        frappe.db.commit()
        return request_id

    def notification(self, recipient):
        doc = frappe.get_doc(dict(doctype='SS97 Client Notification', for_user=recipient,
                                  title='Audit', message='Local access regression')).insert()
        self.records.append((doc.doctype, doc.name))
        frappe.db.commit()
        return doc

    def test_bridge_read_denied_without_doctype_permission(self):
        self.request()
        for user in [self.client, self.unprivileged, 'Guest']:
            with self.subTest(user=user):
                frappe.set_user(user)
                self.assertFalse(frappe.has_permission(api.DOCTYPE, 'read'))
                with self.assertRaises(frappe.PermissionError):
                    api.pending()

    def test_bridge_create_denied_without_doctype_permission(self):
        for user in [self.client, self.unprivileged, 'Guest']:
            with self.subTest(user=user):
                frappe.set_user(user)
                with self.assertRaises(frappe.PermissionError):
                    api.create_request(action='audit', samAccountName='audit',
                                       displayName='Audit', role='Audit')

    def test_bridge_updates_denied_without_doctype_permission(self):
        rid = self.request()
        for method in [api.received, api.processing, api.result]:
            for user in [self.client, self.unprivileged, 'Guest']:
                with self.subTest(method=method.__name__, user=user):
                    frappe.set_user(user)
                    with self.assertRaises(frappe.PermissionError):
                        method(requestId=rid)
        self.assertEqual(frappe.db.get_value(api.DOCTYPE, rid, 'status'), 'PENDING')

    def test_bridge_staff_flow_and_duplicate(self):
        frappe.set_user(self.staff)
        rid = self.request()
        self.assertEqual(api.create_request(action='audit', samAccountName='audit',
                         displayName='Audit', role='Audit', requestId=rid)['status'], 'EXISTS')
        self.assertEqual(api.received(requestId=rid)['status'], 'RECEIVED')
        self.assertEqual(api.processing(requestId=rid)['status'], 'PROCESSING')
        with patch.object(api, '_body', return_value={'status': 'ERROR', 'error': 'local failure'}):
            self.assertEqual(api.result(requestId=rid)['status'], 'ERROR')
        self.assertEqual(frappe.db.count(api.DOCTYPE, {'request_id': rid}), 1)
        self.assertEqual(frappe.db.get_value(api.DOCTYPE, rid, 'error_message'), 'local failure')

    def test_native_issue_assignment_share_and_status(self):
        """Native baseline only: the custom technician portal is not available."""
        from frappe.desk.form import assign_to
        issue = frappe.get_doc(dict(doctype='Issue', subject='Local native assignment baseline',
                                    raised_by=self.client)).insert()
        self.records.append((issue.doctype, issue.name))
        args = dict(doctype='Issue', name=issue.name, assign_to=[self.unprivileged],
                    description='Synthetic native assignment')
        assign_to.add(args)
        assign_to.add(args)
        todos = frappe.get_all('ToDo', filters={'reference_type': 'Issue',
            'reference_name': issue.name, 'allocated_to': self.unprivileged}, pluck='name')
        self.records.extend(('ToDo', name) for name in todos)
        self.assertEqual(len(todos), 1)
        self.assertTrue(frappe.has_permission('Issue', 'read', doc=issue, user=self.unprivileged))
        self.assertFalse(frappe.has_permission('Issue', 'read', doc=issue, user=self.other))
        self.assertFalse(frappe.has_permission('Issue', 'read', doc=issue, user='Guest'))
        self.assertTrue(frappe.db.exists('Notification Log', {'document_type': 'Issue',
                       'document_name': issue.name, 'for_user': self.unprivileged}))
        for name in frappe.get_all('Notification Log', filters={'document_type': 'Issue',
                                   'document_name': issue.name}, pluck='name'):
            self.records.append(('Notification Log', name))
        frappe.set_user(self.unprivileged)
        assign_to.close('Issue', issue.name, self.unprivileged)
        self.assertEqual(frappe.db.get_value('ToDo', todos[0], 'status'), 'Closed')

    def test_bridge_invalid_result_is_not_success(self):
        rid = self.request()
        for status in ['UNKNOWN', 0, None, ['SUCCESS']]:
            with self.subTest(status=status), patch.object(api, '_body', return_value={'status': status}):
                with self.assertRaises(frappe.ValidationError):
                    api.result(requestId=rid)
        self.assertEqual(frappe.db.get_value(api.DOCTYPE, rid, 'status'), 'PENDING')

    def test_notification_customer_cannot_forge_recipient(self):
        frappe.set_user(self.client)
        with self.assertRaises(frappe.PermissionError):
            frappe.get_doc(dict(doctype='SS97 Client Notification', title='Forged',
                                 for_user=self.other)).insert()

    def test_notification_recipient_native_permissions(self):
        own = self.notification(self.client)
        other = self.notification(self.other)
        frappe.set_user(self.client)
        self.assertTrue(frappe.has_permission(own.doctype, 'read', doc=own))
        self.assertTrue(frappe.has_permission(own.doctype, 'write', doc=own))
        self.assertTrue(frappe.has_permission(own.doctype, 'delete', doc=own))
        self.assertTrue(frappe.permissions.get_doc_permissions(own, user=self.client)['read'])
        self.assertFalse(frappe.has_permission(other.doctype, 'read', doc=other))
        self.assertFalse(frappe.has_permission(other.doctype, 'write', doc=other))
        self.assertFalse(frappe.has_permission(other.doctype, 'delete', doc=other))
        rows = frappe.get_list(own.doctype, pluck='name')
        self.assertIn(own.name, rows)
        self.assertNotIn(other.name, rows)

    def test_notification_api_isolation_and_mutations(self):
        own = self.notification(self.client)
        other = self.notification(self.other)
        frappe.set_user(self.client)
        names = [r.name for r in notifications.get_my_notifications()['notifications']]
        self.assertIn(own.name, names)
        self.assertNotIn(other.name, names)
        for method in [notifications.mark_read, notifications.delete_notification]:
            with self.subTest(method=method.__name__):
                with self.assertRaises(frappe.PermissionError):
                    method(other.name)
        notifications.mark_all_read()
        self.assertEqual(frappe.db.get_value(own.doctype, own.name, 'is_read'), 1)
        self.assertEqual(frappe.db.get_value(other.doctype, other.name, 'is_read'), 0)
        notifications.delete_notification(own.name)
        self.assertFalse(frappe.db.exists(own.doctype, own.name))

    def test_notification_guest_denied(self):
        frappe.set_user('Guest')
        for method, args in [(notifications.get_my_notifications, ()),
                             (notifications.mark_all_read, ()),
                             (notifications.mark_read, ('missing',)),
                             (notifications.delete_notification, ('missing',))]:
            with self.subTest(method=method.__name__):
                with self.assertRaises(frappe.PermissionError):
                    method(*args)

    def test_notification_cannot_be_redirected_to_another_user(self):
        own = self.notification(self.client)
        frappe.set_user(self.client)
        own.for_user = self.other
        with self.assertRaises(frappe.PermissionError):
            own.save()

    def test_mark_all_read_is_not_limited_to_one_page(self):
        for _ in range(21):
            self.notification(self.client)
        frappe.set_user(self.client)
        self.assertEqual(notifications.mark_all_read()['updated'], 21)
        self.assertEqual(frappe.db.count('SS97 Client Notification',
                         {'for_user': self.client, 'is_read': 0}), 0)

    def test_native_notification_log_fallback(self):
        for recipient in [self.client, self.other]:
            doc = frappe.get_doc(dict(doctype='Notification Log', type='Alert',
                    for_user=recipient, subject='Local fallback', email_content='Synthetic')).insert()
            self.records.append((doc.doctype, doc.name))
        own, other = self.records[-2:]
        frappe.db.commit()
        frappe.set_user(self.client)
        with patch.object(notifications, '_uses_ss97_notifications', return_value=False):
            names = [r.name for r in notifications.get_my_notifications()['notifications']]
            self.assertIn(own[1], names)
            self.assertNotIn(other[1], names)
            notifications.mark_read(own[1])
            with self.assertRaises(frappe.PermissionError):
                notifications.mark_read(other[1])
            self.assertEqual(frappe.db.get_value(*own, 'read'), 1)
            self.assertEqual(frappe.db.get_value(*other, 'read'), 0)
            with self.assertRaises(frappe.PermissionError):
                notifications.delete_notification(own[1])

    def test_readonly_diagnostics_are_restricted_and_allowlisted(self):
        from softsystem97.diagnostics import collect
        frappe.set_user(self.client)
        with self.assertRaises(frappe.PermissionError):
            collect()
        frappe.set_user(self.staff)
        data = collect(user=self.client)
        self.assertEqual(data['versions']['softsystem97'], '1.0.0')
        self.assertIn('registered_worker_count', data['default_queue'])
        self.assertEqual(set(data['user']), {'status', 'roles'})
        for field in data['user_api_fields'].values():
            self.assertEqual(set(field), {'present', 'hidden', 'permlevel'})

    def test_existing_technician_diagnostic_does_not_grant_or_infer_roles(self):
        from softsystem97.diagnostics import technician_access
        frappe.set_user(self.client)
        with self.assertRaises(frappe.PermissionError):
            technician_access(self.other)
        frappe.set_user(self.staff)
        before = {dt: frappe.db.count(dt) for dt in ['User', 'Role', 'Has Role', 'DocShare']}
        roles = frappe.get_roles(self.client)
        with patch('frappe.set_user', side_effect=AssertionError('No impersonation')):
            data = technician_access(self.client)
        self.assertEqual(data['roles'], roles)
        self.assertIsNone(data['technician_profile_active'])
        self.assertFalse(data['browser_session_verified'])
        self.assertEqual(data['account'].enabled, 1)
        self.assertIn('unknown', data['portal_role_policy'])
        self.assertEqual(before, {dt: frappe.db.count(dt) for dt in before})
        with self.assertRaises(frappe.DoesNotExistError):
            technician_access('nonexistent-audit-user@example.invalid')
        self.assertEqual(before['User'], frappe.db.count('User'))

    def test_technician_diagnostic_reports_native_access_without_mutation(self):
        from softsystem97.diagnostics import technician_access
        from frappe.desk.form import assign_to
        issue = frappe.get_doc(dict(doctype='Issue', subject='Read-only access probe')).insert()
        self.records.append((issue.doctype, issue.name))
        data = technician_access(self.unprivileged, 'Issue', issue.name)
        self.assertFalse(data['ticket']['native_read'])
        self.assertEqual(data['ticket']['open_native_assignment_count'], 0)
        assign_to.add(dict(doctype='Issue', name=issue.name, assign_to=[self.unprivileged]))
        for dt, filters in [('ToDo', {'reference_type': 'Issue', 'reference_name': issue.name}),
                            ('Notification Log', {'document_type': 'Issue', 'document_name': issue.name})]:
            self.records.extend((dt, name) for name in frappe.get_all(dt, filters=filters, pluck='name'))
        self.assertTrue(technician_access(self.unprivileged, 'Issue', issue.name)['ticket']['native_read'])
        self.assertFalse(technician_access(self.other, 'Issue', issue.name)['ticket']['native_read'])

    def test_native_api_generation_requires_system_manager(self):
        from frappe.core.doctype.user.user import generate_keys
        for user in [self.client, self.unprivileged, 'Guest']:
            with self.subTest(user=user):
                frappe.set_user(user)
                # Never generate, read or persist any API credentials in this suite.
                with patch('frappe.generate_hash', side_effect=AssertionError('Must not generate keys')):
                    with self.assertRaises(frappe.PermissionError):
                        generate_keys(self.staff)

    def test_native_api_fields_require_permlevel_one(self):
        meta = frappe.get_meta('User')
        for field in ['api_key', 'api_secret', 'generate_keys']:
            self.assertEqual(meta.get_field(field).permlevel, 1)
        self.assertTrue(any(p.role == 'System Manager' and p.permlevel == 1
                            and p.read and p.write for p in meta.permissions))
