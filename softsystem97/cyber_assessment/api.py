"""Opt-in cyber intake on the same customer Issue bridge as the existing portal."""

import frappe

from .catalog import TIERS, build_ticket, request_payload, required_text


def _enabled():
    config = frappe.conf.get("ss97_cyber_assessment")
    if not isinstance(config, dict) or config.get("enabled") is not True:
        frappe.throw("Service en préparation : réception des demandes non activée.", frappe.PermissionError)


def _manager():
    user = frappe.session.user
    if not user or user == "Guest" or "System Manager" not in frappe.get_roles(user):
        frappe.throw("Supervision réservée à la direction.", frappe.PermissionError)


@frappe.whitelist(methods=["GET"])
def get_catalog():
    """The information-only service catalog can be read without authenticating."""
    return {"tiers": [{"code": key, **value} for key, value in TIERS.items()],
            "active": bool(isinstance(frappe.conf.get("ss97_cyber_assessment"), dict)
                           and frappe.conf.get("ss97_cyber_assessment").get("enabled") is True)}


@frappe.whitelist(methods=["POST"])
def request_assessment(kind, tier, organization, summary, consent, request_id):
    """Only an authenticated, uniquely bound Customer can create a request.

    Reuses the bridge's native Issue authorizations, idempotency receipt and mail.
    Neither this API nor a form grants permission to scan client infrastructure.
    """
    _enabled()
    from softsystem97.integrations.ticket_bridge import policy
    from softsystem97.integrations.ticket_bridge.api import create_ticket

    policy.customer()  # Reject Guest, staff, unmapped or ambiguous Customer.
    accepted = consent is True or consent in ("true", "1", 1)
    try:
        payload = request_payload(kind, tier, organization, summary, accepted)
        token = required_text(request_id, 100, "Identifiant de requête")
    except ValueError as exc:
        frappe.throw(str(exc))
    subject, description = build_ticket(payload)
    # create_ticket rechecks customer, historic business authorization, native
    # Issue write permissions, notification recipient and request_id replay.
    ticket = create_ticket(subject, description, token)
    return {"name": ticket["name"], "status": ticket["status"],
            "kind": payload["kind"], "tier": payload["tier"]}


@frappe.whitelist(methods=["GET"])
def get_admin_queue():
    """Minimal cyber triage; never exposes client text to other portal users."""
    _manager()
    rows = frappe.get_all(
        "Issue", filters={"subject": ["like", "[SS97-CYBER]%"]},
        fields=["name", "subject", "status", "customer", "creation", "modified"],
        order_by="creation desc", limit_page_length=100,
    )
    return {"tickets": rows, "count": len(rows)}


@frappe.whitelist(methods=["GET"])
def get_admin_readiness():
    """Read-only configuration checks without disclosing API secrets or personal data."""
    _manager()
    tech = frappe.conf.get("ss97_tech_os") or {}
    exams = frappe.conf.get("ss97_technician_exams") or {}
    bridge = frappe.conf.get("ss97_ticket_bridge") or {}
    cyber = frappe.conf.get("ss97_cyber_assessment") or {}
    question_doctype = bool(frappe.db.exists("DocType", "SS97 Technician Exam Question"))
    def count_questions(track):
        return frappe.db.count("SS97 Technician Exam Question", {"track": track, "is_active": 1}) if question_doctype else 0
    return {"tech_os_enabled": isinstance(tech, dict) and tech.get("enabled") is True,
            "exams_enabled": isinstance(exams, dict) and exams.get("enabled") is True,
            "ticket_bridge_enabled": (isinstance(bridge, dict)
                                      and bridge.get("enabled") is True),
            "ticket_email_enabled": (isinstance(bridge, dict)
                                     and bridge.get("email_enabled") is True),
            "cyber_intake_enabled": (isinstance(cyber, dict)
                                    and cyber.get("enabled") is True),
            "client_notification_doctype": bool(frappe.db.exists("DocType", "SS97 Client Notification")),
            "n2_question_count": count_questions("L2"),
            "n3_question_count": count_questions("BANK"),
            "n4_question_count": count_questions("CYBER")}
