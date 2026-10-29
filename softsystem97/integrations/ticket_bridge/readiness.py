"""SS97 readiness: administrative metadata only."""
import frappe


@frappe.whitelist(methods=["GET"])
def get_readiness():
    frappe.only_for("System Manager")

    config = frappe.conf.get("ss97_ticket_bridge") or {}
    if not isinstance(config, dict):
        config = {}

    checks = {
        "bridge_enabled": config.get("enabled") is True,
        "historical_enabled": config.get("historical_integration") is True,
        "technician_role_configured": config.get("technician_role") == "SS97 Technician",
        "profile_reviewed": config.get("profile_required") is False,
        "authorizer_path_declared": isinstance(config.get("business_authorizer"), str)
        and config["business_authorizer"].startswith("softsystem97.integrations."),
        "technician_role_exists": False,
        "technician_field_valid": False,
        "issue_workflow_requires_review": True,
        "issue_scripts_require_review": True,
        "payment_ticket_link_verified": False,
        "real_authorizer_verified": False,
        "production_portal_tested": False,
    }

    try:
        checks["technician_role_exists"] = bool(
            frappe.db.exists(
                "Role",
                {"name": "SS97 Technician", "disabled": 0}
            )
        )

        field = frappe.get_meta("Issue").get_field(
            "ss97_technician"
        )

        checks["technician_field_valid"] = bool(
            field
            and field.fieldtype == "Link"
            and field.options == "User"
        )

        checks["issue_workflow_requires_review"] = bool(
            frappe.db.exists(
                "Workflow",
                {"document_type": "Issue", "is_active": 1}
            )
        )

        checks["issue_scripts_require_review"] = bool(
            frappe.db.exists(
                "Server Script",
                {
                    "script_type": "DocType Event",
                    "reference_doctype": "Issue",
                    "disabled": 0
                }
            )
        )

    except Exception:
        return {
            "state": "BLOCKED",
            "reason": "METADATA_UNAVAILABLE",
            "production_ready": False,
            "checks": checks
        }

    blockers = [
        key for key, value in checks.items()
        if (key.endswith("review") and value)
        or (not key.endswith("review") and not value)
    ]

    return {
        "state": "BLOCKED",
        "production_ready": False,
        "checks": checks,
        "blockers": blockers
    }
