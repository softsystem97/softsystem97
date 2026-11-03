"""Synthetic bridge flow for validate_local_mail --bridge, disposable site only."""
import frappe
from softsystem97.integrations.ticket_bridge import api


def produce(account, created):
    suffix = frappe.generate_hash(length=8)
    role = frappe.get_doc(dict(doctype='Role', role_name='Bridge SMTP Lab ' + suffix, desk_access=0)).insert()
    created.append((role.doctype, role.name))
    users = []
    for label, roles in [('client', ['Customer']), ('tech', [role.name])]:
        user = frappe.get_doc(dict(doctype='User', email=f'bridge-smtp-{suffix}-{label}@example.invalid',
            first_name=label, user_type='System User', send_welcome_email=0,
            roles=[{'role': r} for r in roles])).insert()
        created.append((user.doctype, user.name))
        users.append(user.name)
    customer = frappe.get_doc(dict(doctype='Customer', customer_name='Bridge SMTP Lab ' + suffix,
        customer_type='Individual', portal_users=[{'user': users[0]}])).insert()
    created.append((customer.doctype, customer.name))
    old = frappe.conf.get('ss97_ticket_bridge')
    frappe.conf.ss97_ticket_bridge = dict(enabled=True, compatibility_confirmed=True,
        technician_role=role.name, profile_required=False, email_enabled=True, email_account=account.name)
    try:
        frappe.set_user(users[0])
        ticket = api.create_ticket('Bridge SMTP controlled test', 'Synthetic only', 'create')
        created.append(('Issue', ticket['name']))
        assert api.create_ticket('Bridge SMTP controlled test', 'Synthetic only', 'create') == ticket
        frappe.set_user('Administrator')
        api.assign_ticket(ticket['name'], users[1], 'assign')
        api.assign_ticket(ticket['name'], users[1], 'assign')
        frappe.set_user(users[1])
        for status in ['Resolved', 'Closed']:
            current = api.get_ticket(ticket['name'])['ticket']
            args = (ticket['name'], status, current['modified'], status)
            result = api.update_status(*args)
            assert api.update_status(*args) == result
        return frappe.get_doc('Issue', ticket['name'])
    finally:
        frappe.set_user('Administrator')
        # Register all committed references before parent cleanup, even if a probe assertion fails.
        issues = [name for dt, name in created if dt == 'Issue']
        for name in issues:
            for dt, filters in [('ToDo', {'reference_type': 'Issue', 'reference_name': name}),
                    (api.EVENT, {'issue': name}),
                    ('SS97 Client Notification', {'reference_doctype': 'Issue', 'reference_name': name})]:
                created.extend((dt, row) for row in frappe.get_all(dt, filters=filters, pluck='name'))
        if old is None:
            frappe.conf.pop('ss97_ticket_bridge', None)
        else:
            frappe.conf.ss97_ticket_bridge = old
