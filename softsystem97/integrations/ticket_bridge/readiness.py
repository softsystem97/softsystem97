"""Private read-only bridge production preflight; no grants or configuration writes."""
import frappe
from . import policy, issue_script_review, bridge_profile_gate


def _enabled_doctype(name):
    return bool(frappe.db.exists("DocType", name))


def _support_writers():
    # Service-writer candidates: active non-admin users with both identity
    # and Support Team role. Do not return their identities to the browser.
    result = []
    for row in frappe.get_all(
        "User", filters={"enabled": 1, "user_type": "System User"},
        fields=["name"], limit_page_length=2000,
    ):
        if row.name not in ("Administrator", "Guest") and "Support Team" in frappe.get_roles(row.name):
            result.append(row.name)
    return result


@frappe.whitelist(methods=["GET"])
def get_admin_bridge_preflight():
    """Diagnose fail-closed bridge requirements for an authorized System Manager."""
    user = frappe.session.user
    if (not user or user == "Guest"
            or not frappe.db.get_value("User", user, "enabled")
            or "System Manager" not in frappe.get_roles(user)):
        frappe.throw("Accès réservé à la direction.", frappe.PermissionError)

    cfg = frappe.conf.get("ss97_ticket_bridge")
    if not isinstance(cfg, dict):
        cfg = {}
    tech = frappe.conf.get("ss97_tech_os")
    exams = frappe.conf.get("ss97_technician_exams")
    config_role = cfg.get("technician_role")
    existing_roles = []
    for name in ("SS97 Technicien N4", "SS97 Technicien N3", "SS97 Technicien N2",
                 "Technician SoftSystem97", "SS97 Technician"):
        if frappe.db.exists("Role", {"name": name, "disabled": 0}):
            existing_roles.append(name)

    schema = _enabled_doctype("SS97 Ticket Bridge Event")
    event = frappe.get_meta("SS97 Ticket Bridge Event") if schema else None
    issue_present = _enabled_doctype("Issue")
    issue = frappe.get_meta("Issue") if issue_present else None
    customer = issue.get_field("customer") if issue else None
    status = issue.get_field("status") if issue else None
    permitted_statuses = {"Open", "Replied", "On Hold", "Resolved", "Closed"}
    statuses = (
        {item.strip() for item in (status.options or "").splitlines() if item.strip()}
        if status else set()
    )
    try:
        workflow_active = bool(frappe.db.exists(
            "Workflow", {"document_type": "Issue", "is_active": 1}))
    except Exception:
        workflow_active = True  # Fail closed if schema check breaks.
    try:
        issue_scripts = issue_script_review.inventory(frappe)
        issue_state = issue_script_review.approval_state(
            issue_scripts, cfg.get("approved_issue_scripts"),
            cfg.get("issue_scripts_reviewed"),
            cfg.get("issue_scripts_review_reference"))
        issue_inventory_complete = True
        # Only a System Manager may obtain revision hashes; no script code.
        script_revisions = [{
            "name": record["name"],
            "event": record["doctype_event"],
            "sha256": issue_script_review.fingerprint(
                record["name"], record["doctype_event"], record["script"])
        } for record in issue_scripts]
    except (ValueError, TypeError):
        issue_inventory_complete = False
        issue_state = {"approved": False, "count": -1, "unapproved": -1}
        script_revisions = []

    writers = _support_writers()
    designated = cfg.get("writer_user")
    writer_ok = isinstance(designated, str) and designated in writers
    role_ok = (isinstance(config_role, str)
               and config_role.casefold() not in policy.FORBIDDEN_ROLES
               and bool(frappe.db.exists("Role",
                        {"name": config_role, "disabled": 0})))

    conditions = {
        "tech_os_active": isinstance(tech, dict) and tech.get("enabled") is True,
        "exams_service_active": isinstance(exams, dict) and exams.get("enabled") is True,
        "bridge_event_schema": bool(event and all(
            event.has_field(key) for key in ("assignment", "technician", "revoked"))),
        "client_notification_schema": _enabled_doctype("SS97 Client Notification"),
        "issue_customer_link": bool(customer and customer.fieldtype == "Link"
                                    and customer.options == "Customer"),
        "issue_statuses_match": bool(status and status.fieldtype == "Select"
                                     and statuses == permitted_statuses),
        "no_active_issue_workflow": not workflow_active,
        "issue_scripts_inventory_complete": issue_inventory_complete,
        "issue_scripts_approved": issue_state["approved"],
        "role_configured": bool(role_ok),
        "service_writer_configured": bool(writer_ok),
        "profile_adapter_confirmed": bridge_profile_gate.profile_flag_valid(
            config_role, cfg.get("profile_required")),
        "compatibility_signed_off": cfg.get("compatibility_confirmed") is True,
        "bridge_enabled": cfg.get("enabled") is True,
    }
    # Only false/true and non-sensitive role names: never user lists or keys.
    return {
        "checks": conditions,
        "available_technician_roles": existing_roles,
        "support_writer_candidate_count": len(writers),
        "configured_writer_is_valid": bool(writer_ok),
        "issue_scripts_active_count": issue_state["count"],
        "issue_scripts_unapproved_count": issue_state["unapproved"],
        "issue_script_revisions_for_admin": script_revisions,
        "currently_enabled": conditions["bridge_enabled"],
        "activation_prerequisites_met": all(value for key, value in conditions.items()
            if key != "bridge_enabled"),
        "limitations": [
            "L'état de la banque d'examen et la validation réelle des profils N4 sont indépendants.",
            "Un rôle N4 existant ne prouve pas que l'utilisateur candidat l'a obtenu.",
            "Le pont N4 exige un profil CYBER actif, vérifié à chaque accès (profile_required=true).",
            "Les contrats, affectations et mandats restent soumis aux contrôles du serveur.",
            "Les comptes Support Team ne sont pas créés par ce contrôle.",
            "Chaque script Issue doit être examiné par un responsable avant approbation de son empreinte.",
        ],
    }
