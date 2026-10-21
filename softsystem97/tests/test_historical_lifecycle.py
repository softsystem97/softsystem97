"""Native Issue/ToDo tests with an explicitly simulated business authorizer.

No private payment rule or deployed historical controller is validated here.
The Link User custom field is a synthetic supported schema, not a server finding.
"""
from dataclasses import replace
import unittest
from unittest.mock import patch

import frappe

from softsystem97.integrations.ticket_bridge import api, historical, policy
from softsystem97.tests import test_ticket_bridge as bridge_tests


class TestHistoricalLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not frappe.conf.allow_tests or not frappe.local.site.startswith(('audit.', 'test_')):
            raise RuntimeError('Disposable site required')
        frappe.set_user('Administrator')
        cls.field_name = 'Issue-ss97_technician'
        cls.created_field = not frappe.db.exists('Custom Field', cls.field_name)
        if cls.created_field:
            frappe.get_doc(dict(doctype='Custom Field', dt='Issue', fieldname='ss97_technician',
                label='Synthetic technician integration field', fieldtype='Link', options='User')).insert()
        field = frappe.get_meta('Issue').get_field('ss97_technician')
        if not field or field.fieldtype != 'Link' or field.options != 'User':
            raise RuntimeError('Incompatible existing lab field; do not modify it')
        cls.created_role = not frappe.db.exists('Role', 'SS97 Technician')
        if cls.created_role:
            frappe.get_doc(dict(doctype='Role', role_name='SS97 Technician', desk_access=0)).insert()
        bridge_tests.TestTicketBridge.setUpClass.__func__(cls)
        cls.generic_role = cls.role
        for user in [cls.tech, cls.tech2]:
            doc = frappe.get_doc('User', user)
            doc.append('roles', dict(role='SS97 Technician'))
            doc.save()
        frappe.db.commit()
        cls.role = 'SS97 Technician'

    @classmethod
    def tearDownClass(cls):
        cls.role = cls.generic_role
        bridge_tests.TestTicketBridge.tearDownClass.__func__(cls)
        if cls.created_role:
            frappe.delete_doc('Role', 'SS97 Technician')
        if cls.created_field:
            frappe.delete_doc('Custom Field', cls.field_name)
            frappe.clear_cache(doctype='Issue')
        frappe.db.commit()

    def setUp(self):
        bridge_tests.TestTicketBridge.setUp(self)
        frappe.conf.ss97_ticket_bridge.update(historical_integration=True,
            business_authorizer='softsystem97.integrations.ticket_bridge.business_policy.authorize_ticket_operation')
        self.allowed = True
        self.requests = []
        self.provider = patch.object(historical, 'resolve_provider', return_value=self.evaluate)
        self.provider.start()

    def tearDown(self):
        self.provider.stop()
        bridge_tests.TestTicketBridge.tearDown(self)

    create = bridge_tests.TestTicketBridge.create
    assign = bridge_tests.TestTicketBridge.assign

    def evaluate(self, request):
        self.requests.append(request)
        return historical.AuthorizationDecision(self.allowed, request, 'synthetic-policy-v1')

    def assert_denied_without_effect(self, call):
        before = {dt: frappe.db.count(dt) for dt in
                  ['Issue', 'ToDo', api.EVENT, 'Comment', 'SS97 Client Notification']}
        frappe.db.savepoint('denied_business_operation')
        with self.assertRaises(frappe.PermissionError):
            call()
        # Same rollback boundary as an unsuccessful native HTTP request.
        frappe.db.rollback(save_point='denied_business_operation')
        self.assertEqual(before, {dt: frappe.db.count(dt) for dt in before})

    def test_unconfirmed_payment_blocks_assignment_without_side_effect(self):
        ticket = self.create()
        self.allowed = False
        self.assert_denied_without_effect(lambda: self.assign(ticket['name']))
        self.assertFalse(frappe.db.get_value('Issue', ticket['name'], 'ss97_technician'))

    def test_payment_and_ticket_notifications_share_client_authorization(self):
        from softsystem97.integrations.stripe.payment_sync import get_portal_user_for_customer

        self.assertEqual(get_portal_user_for_customer(self.customers[0]), self.client)
        frappe.db.set_value('User', self.client, 'enabled', 0)
        self.assertIsNone(get_portal_user_for_customer(self.customers[0]))
        frappe.db.set_value('User', self.client, 'enabled', 1)
        other = frappe.get_doc('Customer', self.customers[1])
        other.append('portal_users', dict(user=self.client))
        other.save()
        self.assertIsNone(get_portal_user_for_customer(self.customers[0]))
        self.assertIsNone(policy.client_customer_for_user(self.client))

    def test_payment_notification_has_no_fallback_to_customer_email(self):
        from softsystem97.integrations.stripe.payment_sync import get_portal_user_for_customer

        frappe.db.delete('Portal User', {'parent': self.customers[0],
            'parenttype': 'Customer', 'parentfield': 'portal_users'})
        frappe.db.set_value('Customer', self.customers[0], 'email_id', self.client)
        self.assertIsNone(get_portal_user_for_customer(self.customers[0]))

    def test_real_lifecycle_with_simulated_positive_business_decisions(self):
        ticket = self.create()
        self.assign(ticket['name'])
        self.assertEqual(frappe.db.get_value('Issue', ticket['name'], 'ss97_technician'), self.tech)
        frappe.set_user(self.tech)
        self.assertEqual(api.list_tickets()['tickets'][0].name, ticket['name'])
        api.add_intervention(ticket['name'], 'Synthetic intervention', 'work')
        for status in ['Resolved', 'Closed']:
            current = api.get_ticket(ticket['name'])['ticket']
            api.update_status(ticket['name'], status, current['modified'], status)
        frappe.set_user(self.client)
        result = api.get_ticket(ticket['name'], 'client')
        self.assertEqual(result['ticket']['status'], 'Closed')
        self.assertTrue(any('policy:synthetic-policy-v1' in row.detail for row in result['history']))
        self.assertEqual([r.operation for r in self.requests],
                         ['create', 'assign', 'intervention', 'status', 'status'])
        self.assertEqual(len(api.get_notifications('client')['notifications']), 3)

    def test_payment_revocation_blocks_intervention_and_status_but_not_read(self):
        ticket = self.create()
        self.assign(ticket['name'])
        frappe.set_user(self.tech)
        current = api.get_ticket(ticket['name'])['ticket']
        self.allowed = False
        self.assert_denied_without_effect(lambda: api.add_intervention(ticket['name'], 'Denied', 'work'))
        self.assert_denied_without_effect(lambda: api.update_status(
            ticket['name'], 'Resolved', current['modified'], 'status'))
        self.assertEqual(api.get_ticket(ticket['name'])['ticket']['status'], 'Open')

    def test_reassignment_revokes_old_technician_across_all_interfaces(self):
        ticket = self.create()
        self.assign(ticket['name'])
        self.assign(ticket['name'], self.tech2, 'second-tech')
        frappe.set_user(self.tech)
        self.assertEqual(api.list_tickets()['tickets'], [])
        self.assertEqual(api.get_notifications()['notifications'], [])
        self.assert_denied_without_effect(lambda: api.get_ticket(ticket['name']))
        self.assert_denied_without_effect(lambda: api.add_intervention(ticket['name'], 'Denied', 'bad'))
        frappe.set_user(self.tech2)
        self.assertEqual(api.get_ticket(ticket['name'])['ticket']['name'], ticket['name'])
        self.assertEqual(frappe.db.count('SS97 Client Notification',
            {'reference_name': ticket['name'], 'for_user': self.tech2}), 1)

    def test_missing_or_malformed_business_provider_denies_activation(self):
        ticket = self.create()
        with patch.object(historical, 'resolve_provider', side_effect=ImportError('missing')):
            self.assert_denied_without_effect(lambda: self.assign(ticket['name']))
        for result in [True, {'allowed': True}, None]:
            with self.subTest(result=result), patch.object(historical, 'resolve_provider',
                    return_value=lambda request: result):
                self.assert_denied_without_effect(lambda: self.assign(ticket['name']))

    def test_replaced_approval_cannot_revive_when_legacy_field_is_restored(self):
        ticket = self.create()
        self.assign(ticket['name'])
        first = frappe.db.get_value(api.EVENT, {'issue': ticket['name'], 'action': 'assign'}, 'name')
        self.assign(ticket['name'], self.tech2, 'second-tech')
        # A legacy/native writer restoring the field must not resurrect old approval.
        frappe.db.set_value('Issue', ticket['name'], 'ss97_technician', self.tech)
        frappe.set_user(self.tech)
        self.assertEqual(api.list_tickets()['tickets'], [])
        self.assert_denied_without_effect(lambda: api.get_ticket(ticket['name']))
        self.assertEqual(frappe.db.get_value(api.EVENT, first, 'revoked'), 1)

    def test_returning_technician_needs_new_approved_request_not_old_receipt(self):
        ticket = self.create()
        self.assign(ticket['name'], request_id='original-a')
        first = frappe.db.get_value(api.EVENT, {'issue': ticket['name'], 'action': 'assign'}, 'name')
        self.assign(ticket['name'], self.tech2, 'second-b')
        self.assign(ticket['name'], request_id='original-a')  # Receipt only, no reassignment.
        self.assertEqual(frappe.db.get_value('Issue', ticket['name'], 'ss97_technician'), self.tech2)
        self.assertEqual(frappe.db.get_value(api.EVENT, first, 'revoked'), 1)
        self.assign(ticket['name'], request_id='new-approved-a')
        frappe.set_user(self.tech)
        self.assertEqual(api.get_ticket(ticket['name'])['ticket']['name'], ticket['name'])
        frappe.set_user(self.tech2)
        self.assertEqual(api.list_tickets()['tickets'], [])
        self.assertEqual(frappe.db.count('SS97 Client Notification',
            {'reference_name': ticket['name'], 'for_user': self.tech}), 2)

    def test_denied_reassignment_keeps_existing_authorized_technician(self):
        ticket = self.create()
        self.assign(ticket['name'])
        self.allowed = False
        self.assert_denied_without_effect(lambda: self.assign(ticket['name'], self.tech2, 'denied-b'))
        self.assertEqual(frappe.db.get_value('Issue', ticket['name'], 'ss97_technician'), self.tech)
        frappe.set_user(self.tech)
        self.assertEqual(api.get_ticket(ticket['name'])['ticket']['name'], ticket['name'])

    def test_failed_notification_rolls_back_field_revocation_and_new_approval(self):
        ticket = self.create()
        self.assign(ticket['name'])
        before = frappe.db.count(api.EVENT)
        frappe.conf.ss97_ticket_bridge['email_enabled'] = True
        frappe.db.savepoint('failed_reassignment_mail')
        with self.assertRaises(frappe.ValidationError):
            self.assign(ticket['name'], self.tech2, 'failed-mail-b')
        frappe.db.rollback(save_point='failed_reassignment_mail')
        self.assertEqual(frappe.db.count(api.EVENT), before)
        self.assertEqual(frappe.db.get_value('Issue', ticket['name'], 'ss97_technician'), self.tech)
        self.assertTrue(policy.assigned(ticket['name'], self.tech))
        self.assertFalse(policy.assigned(ticket['name'], self.tech2))

    def test_wrong_revision_or_operation_in_decision_is_rejected(self):
        ticket = self.create()
        real = self.evaluate
        for changes in [{'revision': 'stale'}, {'issue': 'OTHER'}, {'operation': 'intervention'},
                        {'actor': self.tech2}, {'technician': self.tech2},
                        {'customer': 'OTHER'}, {'target_status': 'Closed'}]:
            with self.subTest(changes=changes), patch.object(historical, 'resolve_provider',
                    return_value=lambda request: replace(real(request), request=replace(request, **changes))):
                self.assert_denied_without_effect(lambda: self.assign(ticket['name']))
        for changes in [{'allowed': 'true'}, {'policy_version': 'unsafe\nlog'}]:
            with self.subTest(changes=changes), patch.object(historical, 'resolve_provider',
                    return_value=lambda request: replace(real(request), **changes)):
                self.assert_denied_without_effect(lambda: self.assign(ticket['name']))

    def test_noncanonical_role_or_non_user_link_is_never_silently_adapted(self):
        method = frappe.conf.ss97_ticket_bridge['business_authorizer']
        frappe.conf.ss97_ticket_bridge['business_authorizer'] = 'integrations.ss97_tickets.workflow_logic.authorize_ticket_operation'
        with self.assertRaises(frappe.PermissionError):
            policy.settings()
        frappe.conf.ss97_ticket_bridge['business_authorizer'] = method
        frappe.conf.ss97_ticket_bridge['technician_role'] = self.generic_role
        with self.assertRaises(frappe.PermissionError):
            api.list_tickets()
        frappe.conf.ss97_ticket_bridge['technician_role'] = 'SS97 Technician'
        meta = frappe.get_meta('Issue')
        with patch.object(meta, 'get_field', wraps=meta.get_field) as field:
            original = meta.get_field('ss97_technician')
            field.side_effect = lambda name: frappe._dict(fieldtype='Link', options='Unknown Profile') \
                if name == 'ss97_technician' else original
            with self.assertRaises(frappe.PermissionError):
                policy.settings()

    def test_invalid_status_still_rejected_even_if_business_policy_allows(self):
        ticket = self.create()
        self.assign(ticket['name'])
        frappe.set_user(self.tech)
        current = api.get_ticket(ticket['name'])['ticket']
        with self.assertRaises(frappe.ValidationError):
            api.update_status(ticket['name'], 'Closed', current['modified'], 'bad-status')
        self.assertEqual(frappe.db.get_value('Issue', ticket['name'], 'status'), 'Open')

    def test_catalogue_only_module_cannot_authorize_business_operations(self):
        from softsystem97.integrations.ticket_bridge import business_policy

        self.provider.stop()  # Exercise the actual resolver, not the simulated provider.
        self.assertFalse(callable(getattr(business_policy, 'authorize_ticket_operation', None)))
        before = {dt: frappe.db.count(dt) for dt in ['Issue', 'ToDo', api.EVENT]}
        with self.assertRaises(frappe.PermissionError):
            policy.settings()
        self.assertEqual(before, {dt: frappe.db.count(dt) for dt in before})
