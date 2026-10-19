"""Real Frappe v16 integration tests on synthetic users and native Issue records."""
import copy
import unittest
from unittest.mock import patch

import frappe

from softsystem97.integrations.ticket_bridge import api, policy


class TestTicketBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not frappe.conf.allow_tests or not frappe.local.site.startswith(('audit.', 'test_')):
            raise RuntimeError('Disposable audit/test site required')
        frappe.set_user('Administrator')
        cls.suffix = frappe.generate_hash(length=8)
        cls.role = 'SS97 Bridge Lab ' + cls.suffix
        frappe.get_doc(dict(doctype='Role', role_name=cls.role, desk_access=0)).insert()
        cls.users = []
        for label, roles in [('client', ['Customer']), ('other', ['Customer']),
                             ('tech', [cls.role]), ('tech2', [cls.role]), ('none', []),
                             ('candidate', ['Candidat SS97'])]:
            if label == 'candidate' and not frappe.db.exists('Role', 'Candidat SS97'):
                # Do not create a canonical candidate role just for this test.
                roles = []
            email = f'bridge-{cls.suffix}-{label}@example.invalid'
            frappe.get_doc(dict(doctype='User', email=email, first_name=label,
                send_welcome_email=0, user_type='System User', roles=[{'role': r} for r in roles])).insert()
            cls.users.append(email)
        cls.client, cls.other, cls.tech, cls.tech2, cls.none, cls.candidate = cls.users
        cls.customers = []
        for label, user in [('Client', cls.client), ('Other', cls.other)]:
            doc = frappe.get_doc(dict(doctype='Customer', customer_name=f'Bridge {label} {cls.suffix}',
                customer_type='Individual', portal_users=[dict(user=user)] )).insert()
            cls.customers.append(doc.name)
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user('Administrator')
        frappe.db.rollback()
        for name in cls.customers:
            frappe.delete_doc('Customer', name)
        for user in cls.users:
            frappe.delete_doc('User', user)
        frappe.delete_doc('Role', cls.role)
        frappe.db.commit()

    def setUp(self):
        frappe.set_user('Administrator')
        self.old_conf = copy.deepcopy(frappe.conf.get('ss97_ticket_bridge'))
        frappe.conf.ss97_ticket_bridge = dict(enabled=True, compatibility_confirmed=True,
            technician_role=self.role, profile_required=False, email_enabled=False)

    def tearDown(self):
        frappe.set_user('Administrator')
        frappe.db.rollback()
        if self.old_conf is None:
            frappe.conf.pop('ss97_ticket_bridge', None)
        else:
            frappe.conf.ss97_ticket_bridge = self.old_conf
        frappe.clear_cache()

    def create(self, request_id='open', subject='Synthetic bridge Issue'):
        frappe.set_user(self.client)
        return api.create_ticket(subject, 'Controlled description', request_id)

    def assign(self, name, tech=None, request_id='assign'):
        frappe.set_user('Administrator')
        return api.assign_ticket(name, tech or self.tech, request_id)

    def test_disabled_by_default_and_no_side_effect(self):
        frappe.conf.pop('ss97_ticket_bridge')
        before = {dt: frappe.db.count(dt) for dt in ['Issue', 'ToDo', api.EVENT, 'SS97 Client Notification']}
        for method, args in [(api.list_tickets, ()), (api.create_ticket, ('S', 'D', 'key')),
                             (api.assign_ticket, ('missing', self.tech, 'key'))]:
            with self.assertRaises(frappe.PermissionError):
                method(*args)
        self.assertEqual(before, {dt: frappe.db.count(dt) for dt in before})

    def test_configuration_requires_explicit_compatibility_profile_and_safe_role(self):
        for field, value in [('enabled', 'true'), ('compatibility_confirmed', False),
                             ('profile_required', True), ('profile_required', None),
                             ('technician_role', 'System Manager'), ('technician_role', 'Candidat SS97')]:
            with self.subTest(field=field, value=value):
                config = frappe.conf.ss97_ticket_bridge.copy()
                frappe.conf.ss97_ticket_bridge[field] = value
                with self.assertRaises(frappe.PermissionError):
                    policy.settings()
                frappe.conf.ss97_ticket_bridge = config

    def test_guest_and_missing_role_denied(self):
        for user in ['Guest', self.none, self.candidate, self.client]:
            frappe.set_user(user)
            with self.subTest(user=user), self.assertRaises(frappe.PermissionError):
                api.list_tickets()
        frappe.set_user('Guest')
        with self.assertRaises(frappe.PermissionError):
            api.create_ticket('S', 'D', 'key')

    def test_client_create_mapping_confirmation_and_duplicate(self):
        first = self.create()
        second = api.create_ticket('Synthetic bridge Issue', 'Controlled description', 'open')
        self.assertEqual(first['name'], second['name'])
        doc = frappe.get_doc('Issue', first['name'])
        self.assertEqual((doc.customer, doc.raised_by), (self.customers[0], self.client))
        self.assertEqual(frappe.db.count('Issue', {'raised_by': self.client}), 1)
        self.assertEqual(frappe.db.count('SS97 Client Notification', {'reference_name': doc.name}), 1)
        with self.assertRaises(frappe.ValidationError):
            api.create_ticket('Changed payload', 'Controlled description', 'open')

    def test_client_isolation_and_no_email_fallback(self):
        ticket = self.create()
        frappe.set_user(self.other)
        self.assertEqual(api.list_tickets('client')['tickets'], [])
        for name in [ticket['name'], 'missing-ticket']:
            with self.assertRaises(frappe.PermissionError):
                api.get_ticket(name, 'client')
        frappe.set_user('Administrator')
        # Same customer does not imply permission to read another user's ticket.
        doc = frappe.get_doc('Customer', self.customers[0])
        doc.append('portal_users', {'user': self.other})
        doc.save()
        frappe.set_user(self.other)
        with self.assertRaises(frappe.PermissionError):
            api.list_tickets('client')  # Ambiguous Portal User association must fail closed.

    def test_unassigned_then_assigned_and_other_technician_denied(self):
        ticket = self.create()
        frappe.set_user(self.tech)
        self.assertEqual(api.list_tickets()['tickets'], [])
        with self.assertRaises(frappe.PermissionError):
            api.get_ticket(ticket['name'])
        self.assign(ticket['name'])
        frappe.set_user(self.tech)
        self.assertEqual(api.list_tickets()['tickets'][0].name, ticket['name'])
        self.assertEqual(api.get_ticket(ticket['name'])['ticket']['name'], ticket['name'])
        frappe.set_user(self.tech2)
        self.assertEqual(api.list_tickets()['tickets'], [])
        with self.assertRaises(frappe.PermissionError):
            api.get_ticket(ticket['name'])
        with self.assertRaises(frappe.PermissionError):
            api.add_intervention(ticket['name'], 'Foreign write', 'forbidden')

    def test_disabled_technician_or_role_loses_access(self):
        ticket = self.create()
        self.assign(ticket['name'])
        frappe.db.set_value('User', self.tech, 'enabled', 0)
        frappe.set_user(self.tech)
        with self.assertRaises(frappe.PermissionError):
            api.list_tickets()
        frappe.set_user('Administrator')
        frappe.db.set_value('User', self.tech, 'enabled', 1)
        frappe.db.set_value('Role', self.role, 'disabled', 1)
        frappe.set_user(self.tech)
        with self.assertRaises(frappe.PermissionError):
            api.get_ticket(ticket['name'])

    def test_assignment_idempotence_and_no_global_issue_write_grant(self):
        ticket = self.create()
        first = self.assign(ticket['name'])
        retry = self.assign(ticket['name'])
        self.assertEqual(first, retry)
        self.assertTrue(self.assign(ticket['name'], request_id='new-assignment')['already_assigned'])
        self.assertEqual(frappe.db.count('ToDo', {'reference_name': ticket['name'], 'status': 'Open'}), 1)
        self.assertEqual(frappe.db.count('SS97 Client Notification', {'for_user': self.tech,
                         'reference_name': ticket['name']}), 1)
        self.assertFalse(frappe.has_permission('Issue', 'write', doc=ticket['name'], user=self.tech))
        self.assertFalse(frappe.has_permission('Issue', 'read', doc=ticket['name'], user=self.tech))
        self.assertFalse(frappe.db.exists('DocShare', {'share_doctype': 'Issue', 'share_name': ticket['name']}))
        frappe.set_user(self.tech)
        with self.assertRaises(frappe.PermissionError):
            api.assign_ticket(ticket['name'], self.tech2, 'escalate')

    def test_inactive_or_non_technician_assignment_denied(self):
        ticket = self.create()
        for user in [self.client, self.none, 'Guest']:
            with self.subTest(user=user), self.assertRaises(frappe.PermissionError):
                self.assign(ticket['name'], user)
        frappe.set_user('Administrator')
        frappe.db.set_value('User', self.tech, 'enabled', 0)
        with self.assertRaises(frappe.PermissionError):
            self.assign(ticket['name'])

    def test_status_transition_closure_and_retry_without_duplicate_notification(self):
        ticket = self.create()
        self.assign(ticket['name'])
        frappe.set_user(self.tech)
        for index, status in enumerate(['Replied', 'On Hold', 'Resolved', 'Closed']):
            current = api.get_ticket(ticket['name'])['ticket']
            args = (ticket['name'], status, current['modified'], f'status-{index}')
            changed = api.update_status(*args)
            self.assertEqual(api.update_status(*args), changed)
            self.assertEqual(changed['status'], status)
        self.assertEqual(frappe.db.count('SS97 Client Notification', {'reference_name': ticket['name']}), 10)
        frappe.set_user(self.client)
        self.assertEqual(api.get_ticket(ticket['name'], 'client')['ticket']['status'], 'Closed')
        self.assertEqual(len(api.get_ticket(ticket['name'], 'client')['history']), 6)

    def test_stale_and_invalid_status_do_not_mutate_ticket(self):
        ticket = self.create()
        self.assign(ticket['name'])
        frappe.set_user(self.tech)
        with self.assertRaises(api.BridgeConflict):
            api.update_status(ticket['name'], 'Resolved', 'stale', 'stale')
        for status in ['Closed', 'Unknown', 'Open']:
            with self.assertRaises(frappe.ValidationError):
                api.update_status(ticket['name'], status,
                                  api.get_ticket(ticket['name'])['ticket']['modified'], status)
        self.assertEqual(frappe.db.get_value('Issue', ticket['name'], 'status'), 'Open')

    def test_comments_shared_and_escaped_with_private_native_history_excluded(self):
        ticket = self.create()
        self.assign(ticket['name'])
        frappe.get_doc('Issue', ticket['name']).add_comment('Comment', 'PRIVATE INTERNAL NOTE')
        frappe.set_user(self.tech)
        text = '<script>alert(1)</script> Intervention'
        first = api.add_intervention(ticket['name'], text, 'comment')
        self.assertEqual(api.add_intervention(ticket['name'], text, 'comment'), first)
        content = frappe.db.get_value('Comment', first['comment'], 'content')
        self.assertNotIn('<script>', content)
        frappe.set_user(self.client)
        history = api.get_ticket(ticket['name'], 'client')['history']
        self.assertTrue(any('Intervention' in event.detail for event in history))
        self.assertTrue(all('<script>' not in event.detail for event in history))
        self.assertNotIn('PRIVATE INTERNAL NOTE', [event.detail for event in history])
        self.assertEqual(len([event for event in history if event.action == 'comment']), 1)

    def test_cancelled_assignment_revokes_access_without_residual_native_share(self):
        ticket = self.create()
        self.assign(ticket['name'])
        todo = frappe.get_doc('ToDo', {'reference_name': ticket['name'], 'allocated_to': self.tech})
        todo.status = 'Cancelled'
        todo.save()
        frappe.set_user(self.tech)
        self.assertFalse(frappe.has_permission('Issue', 'read', doc=ticket['name']))
        with self.assertRaises(frappe.PermissionError):
            api.get_ticket(ticket['name'])
        self.assertEqual(api.get_notifications()['notifications'], [])
        self.assertEqual(api.list_tickets()['tickets'], [])

    def test_notifications_are_recipient_and_ticket_scoped(self):
        ticket = self.create()
        self.assign(ticket['name'])
        frappe.set_user(self.tech)
        self.assertEqual(len(api.get_notifications()['notifications']), 1)
        frappe.set_user(self.tech2)
        self.assertEqual(api.get_notifications()['notifications'], [])
        frappe.set_user(self.client)
        self.assertEqual(len(api.get_notifications('client')['notifications']), 1)
        frappe.set_user(self.other)
        self.assertEqual(api.get_notifications('client')['notifications'], [])

    def test_mutations_are_post_only_and_no_guest_whitelist(self):
        for method in [api.create_ticket, api.assign_ticket, api.update_status, api.add_intervention]:
            self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[method], ['POST'])
            self.assertNotIn(method, frappe.guest_methods)

    def test_development_page_disabled_and_no_cache(self):
        import importlib
        page = importlib.import_module('softsystem97.www.ss97-dev-technician')
        frappe.conf.ss97_ticket_bridge['enabled'] = False
        with self.assertRaises(frappe.DoesNotExistError):
            page.get_context(frappe._dict())
        frappe.conf.ss97_ticket_bridge['enabled'] = True
        context = page.get_context(frappe._dict())
        self.assertEqual(context.no_cache, 1)

    def test_real_email_queue_only_for_new_events_and_explicit_account(self):
        if frappe.db.exists('Email Account', {'enable_outgoing': 1}):
            self.fail('Disposable site must not have a pre-existing outgoing account')
        account = frappe.get_doc(dict(doctype='Email Account',
            email_account_name='Bridge Lab ' + self.suffix, email_id='sender@example.invalid',
            enable_outgoing=1, default_outgoing=1, smtp_server='127.0.0.1', smtp_port=8026,
            use_tls=0, no_smtp_authentication=1)).insert()
        frappe.conf.ss97_ticket_bridge.update(email_enabled=True, email_account=account.name)
        old_mute = frappe.conf.get('mute_emails')
        frappe.conf.mute_emails = False
        try:
            ticket = self.create()
            self.create()
            self.assign(ticket['name'])
            self.assign(ticket['name'])
            frappe.set_user(self.tech)
            current = api.get_ticket(ticket['name'])['ticket']
            api.update_status(ticket['name'], 'Resolved', current['modified'], 'resolve')
            current = api.get_ticket(ticket['name'])['ticket']
            api.update_status(ticket['name'], 'Closed', current['modified'], 'close')
        finally:
            frappe.conf.mute_emails = old_mute
        queued = frappe.get_all('Email Queue', filters={
            'reference_doctype': 'Issue', 'reference_name': ticket['name']},
            fields=['name', 'status', 'email_account'])
        self.assertEqual(len(queued), 6)
        self.assertTrue(all(row.status == 'Not Sent' for row in queued))
        self.assertTrue(all(row.email_account == account.name for row in queued))

    def test_concurrent_creation_retry_is_one_issue_and_one_confirmation(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        site, sites_path = frappe.local.site, frappe.local.sites_path
        config = copy.deepcopy(frappe.conf.ss97_ticket_bridge)
        barrier = threading.Barrier(2)
        def create_on_connection():
            frappe.init(site=site, sites_path=sites_path)
            frappe.connect()
            frappe.in_test = True
            frappe.flags.in_test = True
            frappe.conf.ss97_ticket_bridge = config.copy()
            frappe.set_user(self.client)
            try:
                barrier.wait(timeout=10)
                for attempt in range(3):
                    try:
                        result = api.create_ticket('Concurrent synthetic ticket', 'Controlled', 'concurrent')
                        frappe.db.commit()
                        return result['name']
                    except api.BridgeConflict:
                        frappe.db.rollback()  # Fresh request transaction, same idempotency key.
                raise AssertionError('Concurrent retry failed to converge')
            except Exception:
                frappe.db.rollback()
                raise
            finally:
                frappe.destroy()
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                names = list(pool.map(lambda _: create_on_connection(), range(2)))
            self.assertEqual(names[0], names[1])
            frappe.db.rollback()
            self.assertEqual(frappe.db.count('Issue', {'raised_by': self.client}), 1)
            self.assertEqual(frappe.db.count('SS97 Client Notification', {'for_user': self.client}), 1)
            self.assertEqual(frappe.db.count(api.EVENT, {'actor': self.client}), 1)
        finally:
            frappe.set_user('Administrator')
            frappe.db.rollback()
            for doctype, filters in [(api.EVENT, {'actor': self.client}),
                    ('SS97 Client Notification', {'for_user': self.client}),
                    ('Issue', {'raised_by': self.client})]:
                for name in frappe.get_all(doctype, filters=filters, pluck='name'):
                    frappe.delete_doc(doctype, name)
            frappe.db.commit()

    def test_installation_role_only_idempotent_and_never_assigns_users(self):
        from softsystem97.integrations.ticket_bridge.install import prepare
        before = {dt: frappe.db.count(dt) for dt in ['User', 'Has Role', 'DocPerm', 'Custom DocPerm']}
        first = prepare(role_name=self.role, dry_run=False, compatibility_confirmed=True)
        second = prepare(role_name=self.role, dry_run=False, compatibility_confirmed=True)
        self.assertEqual(first, second)
        self.assertFalse(first['users_changed'])
        self.assertEqual(first['issue_permissions_added'], [])
        self.assertEqual(before, {dt: frappe.db.count(dt) for dt in before})
        frappe.set_user(self.tech)
        with self.assertRaises(frappe.PermissionError):
            prepare(role_name=self.role)

    def test_existing_workflow_or_issue_producer_blocks_unreviewed_activation(self):
        original = frappe.db.exists
        for doctype in ['Workflow', 'Server Script', 'Notification']:
            def exists(dt, *args, **kwargs):
                return 'Active unadapted component' if dt == doctype else original(dt, *args, **kwargs)
            frappe.conf.ss97_ticket_bridge['email_enabled'] = True
            with self.subTest(doctype=doctype), patch.object(frappe.db, 'exists', side_effect=exists):
                with self.assertRaises(frappe.PermissionError):
                    policy.settings()

    def test_invalid_audience_and_request_key_rejected(self):
        frappe.set_user(self.client)
        for method in [api.session_info, api.list_tickets, api.get_notifications]:
            with self.assertRaises(frappe.PermissionError):
                method(audience='administrator')
        with self.assertRaises(frappe.ValidationError):
            api.create_ticket('S', 'D', '')
        self.assertEqual(frappe.db.count('Issue', {'raised_by': self.client}), 0)

    def test_mail_misconfiguration_rolls_back_whole_request(self):
        frappe.conf.ss97_ticket_bridge.update(email_enabled=True, email_account=None)
        # Match Frappe's POST transaction boundary explicitly, rather than swallowing
        # a service exception and committing a partially executed caller transaction.
        with self.assertRaises(frappe.ValidationError):
            self.create()
        frappe.db.rollback()
        self.assertEqual(frappe.db.count('Issue', {'raised_by': self.client}), 0)
        self.assertEqual(frappe.db.count(api.EVENT, {'actor': self.client}), 0)
        self.assertEqual(frappe.db.count('SS97 Client Notification', {'for_user': self.client}), 0)
