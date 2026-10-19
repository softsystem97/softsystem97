"""Read-only, field-allowlisted diagnostics for an authorized bench console.

Not whitelisted: this does not add an HTTP endpoint. Never export config files,
credential fields, message bodies, recipient lists, job arguments or tracebacks.
"""
import frappe
from frappe.utils import cint


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
