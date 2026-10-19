"""Read-only, field-allowlisted diagnostics for an authorized bench console.

Not whitelisted: this does not add an HTTP endpoint. Never export config files,
credential fields, message bodies, recipient lists, job arguments or tracebacks.
"""
import frappe
from frappe.utils import cint


def technician_access(user, ticket_doctype=None, ticket_name=None):
    """Inspect an existing account; never infer the missing portal's role policy.

    For an authorized bench operator only. No HTTP endpoint, impersonation,
    session/token inspection, account creation or permission modification.
    ticket_name must be the internal name, not an unverified public reference.
    """
    frappe.only_for('System Manager')
    account = frappe.db.get_value('User', user, ['enabled', 'user_type'], as_dict=True)
    if account is None:
        frappe.throw('Existing user not found; no account was created', frappe.DoesNotExistError)
    from frappe.desk.doctype.notification_settings.notification_settings import (
        is_notifications_enabled,
        is_email_notifications_enabled_for_type,
    )
    data = {
        'account': account,
        'roles': frappe.get_roles(user),
        'portal_role_policy': 'unknown_until_portal_source_is_available',
        'technician_profile_active': None,
        'browser_session_verified': False,
        'assignment_notifications': {
            'in_app_enabled': bool(is_notifications_enabled(user)),
            'email_enabled': bool(is_email_notifications_enabled_for_type(user, 'Assignment')),
        },
        'ticket': None,
    }
    if bool(ticket_doctype) != bool(ticket_name):
        frappe.throw('Supply both the confirmed ticket DocType and internal document name')
    if ticket_doctype:
        if not frappe.db.exists(ticket_doctype, ticket_name):
            data['ticket'] = {'exists': False}
        else:
            data['ticket'] = {
                'exists': True,
                'native_read': bool(frappe.has_permission(ticket_doctype, 'read',
                    doc=ticket_name, user=user)),
                'native_write': bool(frappe.has_permission(ticket_doctype, 'write',
                    doc=ticket_name, user=user)),
                'open_native_assignment_count': frappe.db.count('ToDo', {
                    'reference_type': ticket_doctype, 'reference_name': ticket_name,
                    'allocated_to': user, 'status': 'Open'}),
            }
    return data


def queued_mail_conditions(queue_name):
    """Inspect one existing mail's eligibility without sending or reading bodies/errors."""
    frappe.only_for('System Manager')
    from frappe.utils import get_datetime, now_datetime

    row = frappe.db.get_value('Email Queue', queue_name, [
        'status', 'send_after', 'creation', 'retry', 'email_account'], as_dict=True)
    if row is None:
        frappe.throw('Email Queue record not found', frappe.DoesNotExistError)
    now = now_datetime()
    account_name = row.pop('email_account', None)
    account = frappe.db.get_value('Email Account', account_name,
        ['enable_outgoing', 'default_outgoing'], as_dict=True) if account_name else None
    return {
        'queue': row,
        'send_after_due': not row.send_after or get_datetime(row.send_after) < now,
        'undo_window_elapsed': (now - get_datetime(row.creation)).total_seconds() > 10,
        'pending_send_status': row.status in ('Not Sent', 'Partially Sent'),
        'has_recorded_error': bool(frappe.db.exists('Email Queue', {
            'name': queue_name, 'error': ['is', 'set']})),
        'suspend_email_queue': cint(frappe.db.get_default('suspend_email_queue')),
        'emails_muted': bool(frappe.are_emails_muted()),
        'explicit_outgoing_account': account,
        'outgoing_account_selection_verified': account_name is not None and account is not None,
        'smtp_delivery_verified': False,
    }


def collect(queue_name=None, user=None):
    frappe.only_for('System Manager')
    user = user or frappe.session.user
    from frappe.utils.background_jobs import get_queue, get_workers

    versions = {}
    for app in frappe.get_installed_apps():
        try:
            versions[app] = frappe.get_attr(app + '.__version__')
        except (AttributeError, ImportError):
            versions[app] = 'unknown'
    data = {
        'versions': versions,
        'flags': {key: frappe.conf.get(key) for key in (
            'pause_scheduler', 'disable_scheduler', 'maintenance_mode', 'mute_emails',
            'scheduler_tick_interval', 'scheduler_interval')},
        'enable_scheduler': cint(frappe.db.get_single_value('System Settings', 'enable_scheduler')),
        'suspend_email_queue': cint(frappe.db.get_default('suspend_email_queue')),
        'email_retry_limit': frappe.db.get_single_value('System Settings', 'email_retry_limit'),
    }
    data['email_queue'] = frappe.db.get_value('Email Queue', queue_name, [
        'name', 'status', 'retry', 'send_after', 'creation', 'modified', 'priority',
        'reference_doctype', 'reference_name'], as_dict=True) if queue_name else None
    data['mail_scheduled_jobs'] = frappe.get_all('Scheduled Job Type',
        filters={'method': ['in', ['frappe.email.queue.flush', 'frappe.email.queue.retry_sending_emails']]},
        fields=['name', 'method', 'frequency', 'stopped', 'last_execution', 'create_log'])
    for job in data['mail_scheduled_jobs']:
        doc = frappe.get_doc('Scheduled Job Type', job.name)
        job['queue'] = doc.get_queue_name()
        job['recent_logs'] = frappe.get_all('Scheduled Job Log',
            filters={'scheduled_job_type': job.name}, fields=['creation', 'status'],
            order_by='creation desc', limit_page_length=5)
    # Registration/counts do not prove a live process is consuming this queue.
    try:
        queue = get_queue('default')
        data['default_queue'] = {
            'pending_count': queue.count,
            'registered_worker_count': len(get_workers(queue=queue)),
        }
    except Exception as exc:
        data['default_queue'] = {'unavailable_error_type': type(exc).__name__}
    data['user'] = {
        'status': frappe.db.get_value('User', user, ['enabled', 'user_type'], as_dict=True),
        'roles': frappe.get_roles(user) if frappe.db.exists('User', user) else [],
    }
    meta = frappe.get_meta('User')
    data['user_api_fields'] = {field: {
        'present': bool(meta.get_field(field)),
        'hidden': meta.get_field(field).hidden if meta.get_field(field) else None,
        'permlevel': meta.get_field(field).permlevel if meta.get_field(field) else None,
    } for field in ['api_access', 'api_key', 'api_secret', 'generate_keys']}
    data['user_scripts'] = frappe.get_all('Client Script', filters={'dt': 'User'},
                                        fields=['name', 'enabled', 'modified'])
    data['user_property_setters'] = frappe.get_all('Property Setter',
        filters={'doc_type': 'User', 'field_name': ['in', list(data['user_api_fields'])]},
        fields=['field_name', 'property', 'modified'])
    return data
