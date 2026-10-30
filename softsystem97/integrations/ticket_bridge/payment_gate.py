"""Fail-closed Stripe payment proof for an SS97 Issue (no automatic activation).

Read-only evidence verifier. It is NOT an authorization provider: business
workflow, actor permissions and native Frappe controls must also approve actions.
"""
from decimal import Decimal, InvalidOperation
import json

SUCCESS_EVENT_TYPES = (
    'checkout.session.completed', 'payment_intent.succeeded', 'invoice.paid',
)


def _amount(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _value(row, key, default=None):
    return row.get(key, default) if isinstance(row, dict) else getattr(row, key, default)


def invoice_is_fully_stripe_paid(invoice, events, payment_entries, allocations):
    """No trust in a client flag/redirect; only submitted, linked Stripe PE sums.

    Parameters are server-fetched records, never HTTP-supplied evidence.
    Keys: payment_entries indexed by Payment Entry name; allocations keyed likewise.
    """
    total = _amount(_value(invoice, 'grand_total'))
    due = _amount(_value(invoice, 'outstanding_amount'))
    if (total is None or due is None or total <= 0 or due < 0 or due > Decimal('0.01')
            or _value(invoice, 'docstatus') != 1 or not _value(invoice, 'customer')
            or not _value(invoice, 'currency') or _value(invoice, 'ss97_payment_status') != 'paid'):
        return False
    received = Decimal('0')
    used = set()
    for event in events:
        if (_value(event, 'status') != 'Success' or _value(event, 'livemode') not in (1, True)
                or _value(event, 'event_type') not in SUCCESS_EVENT_TYPES
                or str(_value(event, 'currency') or '').upper() != str(_value(invoice, 'currency')).upper()):
            continue
        try:
            result = json.loads(_value(event, 'result') or '')
        except (TypeError, ValueError):
            continue
        if not isinstance(result, dict) or result.get('invoice') != _value(invoice, 'name'):
            continue
        pe_name = result.get('payment_entry')
        if not isinstance(pe_name, str) or not pe_name or pe_name in used:
            continue
        pe = payment_entries.get(pe_name)
        if (pe is None or _value(pe, 'docstatus') != 1 or _value(pe, 'payment_type') != 'Receive'
                or _value(pe, 'party_type') != 'Customer'
                or _value(pe, 'party') != _value(invoice, 'customer')):
            continue
        rows = allocations.get(pe_name, [])
        if not rows:
            continue
        allocated = Decimal('0')
        for row in rows:
            if (_value(row, 'reference_doctype') != 'Sales Invoice'
                    or _value(row, 'reference_name') != _value(invoice, 'name')):
                allocated = Decimal('-1')
                break
            part = _amount(_value(row, 'allocated_amount'))
            if part is None or part <= 0:
                allocated = Decimal('-1')
                break
            allocated += part
        if allocated <= 0:
            continue
        used.add(pe_name)
        received += allocated
    return received >= total - Decimal('0.01')


def issue_has_verified_stripe_payment(issue_name):
    """Read only. Missing/ambiguous links, refunds or metadata => deny."""
    import frappe

    if not isinstance(issue_name, str) or not issue_name:
        return False
    issue_meta = frappe.get_meta('Issue')
    invoice_meta = frappe.get_meta('Sales Invoice')
    if (not issue_meta.has_field('customer')
            or not invoice_meta.has_field('ss97_linked_issue')
            or not invoice_meta.has_field('ss97_payment_status')):
        return False

    # Production metadata audit: the confirmed link is on Sales Invoice,
    # not Issue.ss97_invoice_name. Never assume a missing Issue custom field.
    issue = frappe.db.get_value('Issue', issue_name, ['name', 'customer'], as_dict=True)
    customer = _value(issue, 'customer')
    if _value(issue, 'name') != issue_name or not customer:
        return False

    # A payment must point to ONE unambiguous invoice for this exact ticket.
    # Two matches are enough to deny, even if one is paid.
    invoices = frappe.get_all(
        'Sales Invoice',
        filters={'ss97_linked_issue': issue_name},
        fields=['name', 'ss97_linked_issue', 'customer', 'currency',
                'grand_total', 'outstanding_amount', 'docstatus',
                'ss97_payment_status'],
        limit_page_length=2,
    )
    if len(invoices) != 1:
        return False
    invoice = invoices[0]
    invoice_name = _value(invoice, 'name')
    if (not invoice_name
            or _value(invoice, 'ss97_linked_issue') != issue_name
            or _value(invoice, 'customer') != customer):
        return False

    # Refunds and disputes must be assessed before release; a positive webhook
    # followed by a refund cannot justify a future technician intervention.
    canceled = frappe.get_all('SS97 Stripe Event', filters={
        'invoice': invoice_name, 'status': 'Success', 'livemode': 1,
        'event_type': ['in', ['charge.refunded', 'charge.dispute.created']],
    }, fields=['name'], limit_page_length=1)
    if canceled:
        return False
    events = frappe.get_all('SS97 Stripe Event', filters={
        'invoice': invoice_name, 'status': 'Success', 'livemode': 1,
        'event_type': ['in', list(SUCCESS_EVENT_TYPES)],
    }, fields=['status', 'livemode', 'event_type', 'currency', 'result'], limit_page_length=100)
    payment_names = set()
    for event in events:
        try:
            result = json.loads(_value(event, 'result') or '')
        except (TypeError, ValueError):
            continue
        if isinstance(result, dict) and isinstance(result.get('payment_entry'), str):
            payment_names.add(result['payment_entry'])
    payment_entries = {}
    allocations = {}
    for pe_name in payment_names:
        entry = frappe.db.get_value('Payment Entry', pe_name,
            ['docstatus', 'payment_type', 'party_type', 'party'], as_dict=True)
        if entry:
            payment_entries[pe_name] = entry
            allocations[pe_name] = frappe.get_all('Payment Entry Reference', filters={
                'parent': pe_name, 'parenttype': 'Payment Entry'},
                fields=['reference_doctype', 'reference_name', 'allocated_amount'], limit_page_length=100)
    return invoice_is_fully_stripe_paid(invoice, events, payment_entries, allocations)


def require_paid_intervention(issue_name, operation):
    """Enforce paid-before-work only on an explicitly reviewed configuration.

    The bridge is currently an opt-in replacement. The feature flag is OFF
    unless ss97_ticket_bridge.enforce_paid_interventions is literal True.
    This guard never grants access and never writes to site data. The caller
    must independently enforce roles, ownership, workflow and assignment.
    """
    import frappe

    if operation not in ('assign', 'status', 'intervention'):
        frappe.throw('Operation de passerelle inconnue.', frappe.PermissionError)

    config = frappe.conf.get('ss97_ticket_bridge') or {}
    if not isinstance(config, dict):
        frappe.throw('Configuration de la passerelle invalide.', frappe.PermissionError)
    if config.get('enforce_paid_interventions') is not True:
        return False  # Inactive until the predeployment review explicitly opts in.

    # Authorization must NEVER be decided by an HTTP-supplied "paid" field.
    # Missing site metadata, payment evidence or database permissions deny.
    try:
        verified = issue_has_verified_stripe_payment(issue_name)
    except Exception:
        verified = False

    if verified is not True:
        frappe.throw(
            'Intervention bloquee : paiement LIVE de la facture non prouve.',
            frappe.PermissionError,
        )
    return True
