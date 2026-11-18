"""Fail-closed provider for SS97's historical authorization contract.

Inactive until deployed and explicitly configured by an authorized administrator.
It cannot grant site permissions, change records or activate LIVE payments.
"""
def authorize_ticket_operation(request):
    import frappe
    from .historical import AuthorizationRequest, AuthorizationDecision

    if not isinstance(request, AuthorizationRequest):
        frappe.throw("Demande metier invalide.", frappe.PermissionError)

    def decision(allow=False):
        return AuthorizationDecision(
            allowed=(allow is True),
            request=request,
            policy_version="stripe-posted-invoice-v1",
        )

    config = frappe.conf.get("ss97_ticket_bridge") or {}
    if not isinstance(config, dict) or config.get("enforce_paid_interventions") is not True:
        return decision()
    if request.actor in ("", "Guest") or request.actor != frappe.session.user:
        return decision()

    # Creation is permitted before payment, but only after the pre-existing
    # enforce_confirmed_constraints() proved the caller's customer ownership.
    if request.operation == "create":
        return decision(
            not request.issue and not request.revision and not request.status
            and not request.technician and bool(request.customer)
            and request.target_status == "Open"
        )

    # Cockpit/exception operations remain denied until their private workflows
    # are explicitly validated. No client-supplied paid flag is trusted.
    if request.operation not in ("assign", "status", "intervention"):
        return decision()
    if not request.issue or not request.customer or not request.technician:
        return decision()

    try:
        from .payment_gate import issue_has_verified_stripe_payment
        paid = issue_has_verified_stripe_payment(request.issue) is True
    except Exception:
        paid = False
    return decision(paid)
