"""Confirmed historical catalogue constraints, NOT a business authorizer.

No authorize_ticket_operation is provided: payment proof, actor-specific action
rights and deployed Workflow/Server Scripts are not in the received sources.
Never register catalogue predicates as business_authorizer. No activation occurs.
"""


def native_status(ticket_status):
    """Reject unknown/unmapped states rather than silently reopening as Open."""
    from integrations.ss97_tickets.specs import STATUS_TO_NATIVE

    if not isinstance(ticket_status, str) or ticket_status not in STATUS_TO_NATIVE:
        raise ValueError("Statut historique absent du mapping confirmé.")
    return STATUS_TO_NATIVE[ticket_status]


def is_declared_transition(source, target):
    """Catalogue edge only; says nothing about role, payment, consent or ownership.

    Keep exact runtime states: merging aliases could broaden the original graph.
    """
    from integrations.ss97_tickets.specs import STATUS_ACTIONS

    return any(
        destination == target for _, destination in STATUS_ACTIONS.get(source, [])
    )


def catalogue_gaps():
    """Expose source contradictions for review, never resolve them by guessing."""
    from integrations.ss97_tickets.specs import (
        STATUS_ALIAS_TO_OFFICIAL,
        STATUS_TO_NATIVE,
        TICKET_STATUSES,
    )

    return {
        "unmapped_statuses": [s for s in TICKET_STATUSES if s not in STATUS_TO_NATIVE],
        "alias_native_conflicts": [
            alias
            for alias, canonical in STATUS_ALIAS_TO_OFFICIAL.items()
            if alias in STATUS_TO_NATIVE
            and canonical in STATUS_TO_NATIVE
            and STATUS_TO_NATIVE[alias] != STATUS_TO_NATIVE[canonical]
        ],
        "authorization_provider_available": False,
    }


def enforce_confirmed_constraints(request, doc=None):
    """Necessary server guards only; never grants a business authorization.

    The private provider must still prove payment, exemptions and approved
    deployed transitions. A satisfied guard is deliberately not a Decision.
    """
    import frappe
    from . import policy
    from .historical import AuthorizationRequest

    def deny():
        frappe.throw('Préconditions serveur historiques non démontrées.', frappe.PermissionError)

    operations = {'create', 'assign', 'status', 'intervention',
        'cockpit.start', 'cockpit.pause', 'cockpit.resume', 'cockpit.complete',
        'cockpit.submit_close', 'cockpit.admin_clear_security',
        'cockpit.close_remote', 'cockpit.gwen_emit'}
    if not isinstance(request, AuthorizationRequest):
        deny()
    if (any(not isinstance(value, str) for value in vars(request).values())
            or request.operation not in operations
            or request.actor != frappe.session.user):
        deny()
    policy.active_user()
    if request.operation == 'create':
        user, customer = policy.customer()
        if (doc is not None or request.issue or request.revision or request.status
                or request.technician or request.customer != customer
                or request.actor != user or request.target_status != 'Open'):
            deny()
        return
    if (doc is None or doc.doctype != 'Issue' or request.issue != doc.name
            or request.revision != str(doc.modified)
            or request.customer != (doc.customer or '') or request.status != doc.status):
        deny()
    if request.operation in ('assign', 'cockpit.admin_clear_security'):
        policy.dispatcher()
        doc.check_permission('write')
        if request.operation == 'assign':
            policy.technician(request.technician)
            if doc.status == 'Closed':
                deny()
    elif request.operation == 'cockpit.close_remote' and policy.client_customer_for_user(request.actor):
        policy.authorize(doc, 'client')
        if request.technician != request.actor:
            deny()
    else:
        policy.authorize(doc, 'technician')
        if request.technician != request.actor:
            deny()
    if request.operation == 'status' and request.target_status not in policy.TRANSITIONS.get(doc.status, []):
        deny()
    if request.operation == 'intervention' and doc.status == 'Closed':
        deny()
    if request.operation in ('cockpit.start', 'cockpit.resume'):
        # Both checks are explicitly present in the recovered cockpit. Missing
        # custom metadata is not evidence that a suspension is inactive.
        if not all(doc.meta.has_field(field) for field in ('ss97_security_suspend', 'ss97_ticket_status')):
            deny()
        if (type(doc.get('ss97_security_suspend')) not in (int, bool)
                or doc.get('ss97_security_suspend') != 0
                or not doc.get('ss97_ticket_status')
                or doc.get('ss97_ticket_status') == 'Suspendu — risque sécurité'):
            deny()
