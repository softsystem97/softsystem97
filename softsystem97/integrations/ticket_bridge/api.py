"""Scoped service capabilities over native Issue/ToDo, disabled by default.

No Issue DocPerm is granted. Each privileged write below follows identity, scope,
allowlist and transaction checks; native validation/workflow hooks still run.
"""
import hashlib
from functools import wraps
import json
from html import escape

import frappe
from frappe.utils import strip_html

from . import policy

EVENT = 'SS97 Ticket Bridge Event'
FIELDS = ['name', 'subject', 'status', 'modified']


class BridgeConflict(frappe.ValidationError):
    http_status_code = 409


def transaction_conflict(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except (frappe.QueryDeadlockError, frappe.QueryTimeoutError, frappe.TimestampMismatchError):
            # Let the HTTP request boundary roll back; never commit or roll back
            # somebody else's transaction inside a service capability.
            raise BridgeConflict('Conflit temporaire. Réessayez avec la même clé de requête.') from None
    return wrapped


def _text(value, label, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        frappe.throw(f'{label} invalide.')
    return value.strip()


def _issue(name, lock=False):
    name = _text(name, 'Ticket', 140)
    exists = frappe.db.get_value('Issue', name, 'name', for_update=True) if lock else frappe.db.exists('Issue', name)
    if not exists:
        frappe.throw('Ticket inaccessible.', frappe.PermissionError)
    return frappe.get_doc('Issue', name, for_update=lock)


def _begin(action, request_id, data):
    """Serialize per actor in the request transaction, then use a unique receipt.

    Locking reads avoid stale repeatable-read snapshots on concurrent retries.
    No commit: receipt, Issue, history and mail succeed or roll back together.
    """
    user = policy.active_user()
    request_id = _text(request_id, 'Identifiant de requête', 100)
    name = hashlib.sha256(f'{user}\0{request_id}'.encode()).hexdigest()
    digest = hashlib.sha256(json.dumps([action, data], sort_keys=True).encode()).hexdigest()
    frappe.db.get_value('User', user, 'name', for_update=True)
    if frappe.db.get_value(EVENT, name, 'name', for_update=True):
        event = frappe.get_doc(EVENT, name, for_update=True)
        if event.actor != user or event.action != action or event.request_hash != digest:
            frappe.throw('Identifiant de requête déjà utilisé avec un autre contenu.')
        if not event.response_json:
            frappe.throw('Requête incomplète, réessayer plus tard.')
        return event, json.loads(event.response_json)
    event = frappe.get_doc(dict(doctype=EVENT, name=name, actor=user, action=action,
                                request_hash=digest))
    event.insert(ignore_permissions=True)
    return event, None


def _finish(event, doc, detail, response):
    event.issue = doc.name
    event.detail = detail
    event.response_json = json.dumps(response, default=str)
    event.save(ignore_permissions=True)
    return response


def _notify(doc, users, title):
    config = policy.settings()
    for user in sorted({user for user in users if user}):
        if not user or not frappe.db.get_value('User', user, 'enabled'):
            continue
        # Narrow producer: recipients are calculated on the server, never HTTP input.
        frappe.get_doc(dict(doctype='SS97 Client Notification', for_user=user,
            title=title, message=f'{doc.name} — {doc.status}', customer=doc.customer,
            reference_doctype='Issue', reference_name=doc.name)).insert(ignore_permissions=True)
        if config.get('email_enabled') is True:
            account_name = _text(config.get('email_account'), 'Compte sortant', 140)
            account = frappe.db.get_value('Email Account', account_name,
                                         ['email_id', 'enable_outgoing'], as_dict=True)
            if not account or not account.enable_outgoing:
                frappe.throw('Compte sortant validé requis ; opération annulée.')
            # Queue only new events. No flush, resend, historical sweep or early commit.
            frappe.sendmail(recipients=[user], sender=account.email_id, subject=title,
                            message=escape(f'{doc.name} — {doc.status}'), delayed=True,
                            reference_doctype='Issue', reference_name=doc.name)


def _client_recipient(doc):
    # Do not mail arbitrary raised_by addresses on historical tickets.
    user = doc.raised_by
    return user if (user and frappe.db.exists('Portal User', {'user': user,
        'parenttype': 'Customer', 'parent': doc.customer}) and
        frappe.db.get_value('User', user, 'enabled')) else None


def _result(doc, audience):
    return {field: str(doc.get(field) or '') for field in FIELDS} | {
        'description': strip_html(doc.description or ''),
        'allowed_statuses': policy.TRANSITIONS.get(doc.status, []) if audience == 'technician' else [],
    }


@frappe.whitelist(methods=['GET'])
def session_info(audience='technician'):
    policy.settings()
    user = policy.actor(audience)
    return {'user': user, 'audience': audience}


@frappe.whitelist(methods=['GET'])
def list_tickets(audience='technician', offset=0):
    policy.settings()
    offset = max(0, min(int(offset), 100000))
    if audience == 'technician':
        user = policy.technician()
        # Assignment bounds the service query; no global Issue read grant.
        rows = frappe.db.sql('''SELECT i.name, i.subject, i.status, i.modified
            FROM `tabIssue` i WHERE EXISTS (SELECT 1 FROM `tabToDo` t
            WHERE t.reference_type='Issue' AND t.reference_name=i.name
              AND t.allocated_to=%s AND t.status='Open')
            ORDER BY i.modified DESC, i.name DESC LIMIT 50 OFFSET %s''', (user, offset), as_dict=True)
    elif audience == 'client':
        user, client = policy.customer()
        rows = frappe.get_all('Issue', filters={'customer': client, 'raised_by': user},
            fields=FIELDS, order_by='modified desc, name desc', start=offset, page_length=50)
    else:
        frappe.throw('Espace invalide.', frappe.PermissionError)
    return {'tickets': rows, 'offset': offset, 'page_size': 50}


@frappe.whitelist(methods=['GET'])
def get_ticket(name, audience='technician'):
    policy.actor(audience)
    doc = _issue(name)
    policy.authorize(doc, audience)
    history = frappe.get_all(EVENT, filters={'issue': doc.name},
        fields=['creation', 'action', 'detail'], order_by='creation desc, name desc', page_length=200)
    history.reverse()
    return {'ticket': _result(doc, audience), 'history': history}


@frappe.whitelist(methods=['POST'])
@transaction_conflict
def create_ticket(subject, description, request_id):
    user, client = policy.customer()
    subject = _text(subject, 'Sujet', 140)
    description = _text(description, 'Description', 10000)
    event, previous = _begin('create', request_id, [subject, description])
    if previous is not None:
        policy.authorize(_issue(previous['name'], lock=True), 'client')
        return previous
    doc = frappe.get_doc(dict(doctype='Issue', subject=subject, description=escape(description),
                             customer=client, raised_by=user, status='Open'))
    # Client/customer are session-derived. No user-supplied fields, assignment or identity.
    doc.insert(ignore_permissions=True)
    _notify(doc, [user], 'Confirmation d’ouverture du ticket')
    return _finish(event, doc, 'Ticket ouvert', _result(doc, 'client'))


@frappe.whitelist(methods=['POST'])
@transaction_conflict
def assign_ticket(name, technician, request_id):
    policy.dispatcher()
    policy.technician(technician)
    doc = _issue(name, lock=True)
    doc.check_permission('write')
    if doc.status == 'Closed':
        frappe.throw('Un ticket clôturé ne peut pas être attribué.')
    event, previous = _begin('assign', request_id, [name, technician])
    if previous is not None:
        return previous
    filters = {'reference_type': 'Issue', 'reference_name': name,
               'allocated_to': technician, 'status': 'Open'}
    existing = frappe.db.exists('ToDo', filters)
    if not existing:
        # Native ToDo lifecycle updates _assign and writes the assignment timeline.
        # Deliberately no assign_to.add: its independent mail producer would duplicate ours.
        frappe.get_doc(dict(doctype='ToDo', **filters, assigned_by=frappe.session.user,
                            description='Intervention Soft System 97')).insert()
        _notify(doc, [technician], 'Nouvelle intervention attribuée')
    return _finish(event, doc, 'Intervention attribuée', {'name': name, 'already_assigned': bool(existing)})


@frappe.whitelist(methods=['POST'])
@transaction_conflict
def update_status(name, status, expected_modified, request_id):
    policy.technician()
    doc = _issue(name, lock=True)
    policy.authorize(doc, 'technician')
    status = _text(status, 'Statut', 30)
    event, previous = _begin('status', request_id, [name, status, expected_modified])
    if previous is not None:
        return previous
    if str(doc.modified) != expected_modified:
        frappe.throw('Ticket modifié entre-temps. Rechargez avant de réessayer.', frappe.TimestampMismatchError)
    if status not in policy.TRANSITIONS.get(doc.status, []):
        frappe.throw('Transition de statut interdite.')
    doc.status = status  # The only writable Issue field exposed by this capability.
    doc.save(ignore_permissions=True)
    doc.add_comment('Comment', escape(f'Statut : {status}'))
    users = [r.allocated_to for r in frappe.get_all('ToDo', filters={
        'reference_type': 'Issue', 'reference_name': name, 'status': 'Open'}, fields=['allocated_to'])
        if (frappe.db.get_value('User', r.allocated_to, 'enabled') and
            policy.settings()['technician_role'] in frappe.get_roles(r.allocated_to))]
    _notify(doc, users + [_client_recipient(doc)],
            'Ticket clôturé' if status == 'Closed' else 'Avancement du ticket')
    return _finish(event, doc, status, _result(doc, 'technician'))


@frappe.whitelist(methods=['POST'])
@transaction_conflict
def add_intervention(name, content, request_id, audience='technician'):
    policy.actor(audience)
    doc = _issue(name, lock=True)
    policy.authorize(doc, audience)
    if doc.status == 'Closed':
        frappe.throw('Ticket clôturé : commentaire refusé.')
    content = _text(strip_html(_text(content, 'Commentaire', 5000)), 'Commentaire', 5000)
    event, previous = _begin('comment', request_id, [name, content, audience])
    if previous is not None:
        return previous
    comment = doc.add_comment('Comment', escape(content))
    return _finish(event, doc, content, {'name': name, 'comment': comment.name})


@frappe.whitelist(methods=['GET'])
def get_notifications(audience='technician', offset=0):
    policy.settings()
    user = policy.actor(audience)
    rows = frappe.get_all('SS97 Client Notification', filters={
        'for_user': user, 'reference_doctype': 'Issue'},
        fields=['name', 'title', 'message', 'is_read', 'reference_name', 'creation'],
        order_by='creation desc', start=max(0, min(int(offset), 100000)), page_length=50)
    allowed = []
    for row in rows:
        try:
            policy.authorize(_issue(row.reference_name), audience)
        except frappe.PermissionError:
            continue
        allowed.append(row)
    return {'notifications': allowed}
