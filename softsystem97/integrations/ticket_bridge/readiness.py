"""Read-only, administrator-only production readiness for the SS97 ticket bridge.

The result is NEVER a deployment or payment activation. Explicit reviews are
stored in server site configuration and must not come from HTTP parameters.
Payment authorization remains controlled separately by the server.
"""
import frappe


@frappe.whitelist(methods=["GET"])
def get_readiness():
    frappe.only_for("System Manager")

    config = frappe.conf.get("ss97_ticket_bridge") or {}
    if not isinstance(config, dict):
        config = {}
    approvals = config.get("release_approvals") or {}
    if not isinstance(approvals, dict):
        approvals = {}

    authorizer_path = config.get("business_authorizer")
    approved_authorizer = (
        authorizer_path ==
        "softsystem97.integrations.ticket_bridge.live_authorizer.authorize_ticket_operation"
    )

    checks = {
        "bridge_enabled": config.get("enabled") is True,
        "historical_enabled": config.get("historical_integration") is True,
        "paid_intervention_gate_enabled": config.get("enforce_paid_interventions") is True,
        "technician_role_configured": config.get("technician_role") == "SS97 Technician",
        "profile_reviewed": config.get("profile_required") is False,
        "authorizer_path_declared": approved_authorizer,
        "technician_role_exists": False,
        "technician_field_valid": False,
        "issue_workflow_requires_review": True,
        "issue_scripts_require_review": True,
        "payment_ticket_link_verified": False,
        "real_authorizer_verified": False,
        "production_portal_tested": approvals.get("production_portal_tested") is True,
        "stripe_webhook_delivery_verified": approvals.get("stripe_webhook_delivery_verified") is True,
        "stripe_accounting_reconciled": approvals.get("stripe_accounting_reconciled") is True,
    }

    try:
        checks["technician_role_exists"] = bool(
            frappe.db.exists("Role", {"name": "SS97 Technician", "disabled": 0})
        )
        issue_meta = frappe.get_meta("Issue")
        invoice_meta = frappe.get_meta("Sales Invoice")
        field = issue_meta.get_field("ss97_technician")
        checks["technician_field_valid"] = bool(
            field and field.fieldtype == "Link" and field.options == "User"
        )

        has_workflow = bool(frappe.db.exists(
            "Workflow", {"document_type": "Issue", "is_active": 1}
        ))
        has_script = bool(frappe.db.exists(
            "Server Script",
            {"script_type": "DocType Event",
             "reference_doctype": "Issue", "disabled": 0}
        ))
        checks["issue_workflow_requires_review"] = (
            has_workflow and approvals.get("issue_workflow_reviewed") is not True
        )
        checks["issue_scripts_require_review"] = (
            has_script and approvals.get("issue_scripts_reviewed") is not True
        )

        linked = bool(
            issue_meta.has_field("customer")
            and invoice_meta.has_field("ss97_linked_issue")
            and invoice_meta.has_field("ss97_payment_status")
            and frappe.db.exists("DocType", "SS97 Stripe Event")
            and frappe.db.exists("DocType", "Payment Entry")
        )
        checks["payment_ticket_link_verified"] = (
            linked and approvals.get("payment_ticket_link_verified") is True
        )

        # Never resolve an arbitrary dotted path from an HTTP query.
        if approved_authorizer:
            checks["real_authorizer_verified"] = (
                callable(frappe.get_attr(authorizer_path))
                and approvals.get("real_authorizer_verified") is True
            )

    except Exception:
        return {
            "state": "BLOCKED",
            "reason": "METADATA_UNAVAILABLE",
            "production_ready": False,
            "checks": checks,
        }

    blockers = [
        key for key, value in checks.items()
        if (key.endswith("requires_review") and value)
        or (not key.endswith("requires_review") and not value)
    ]

    ready = not blockers
    return {
        "state": "READY_FOR_RELEASE_REVIEW" if ready else "BLOCKED",
        "production_ready": ready,
        "checks": checks,
        "blockers": blockers,
        "note": "Readiness only. Does not deploy, configure Stripe, or authorize payments.",
    }
