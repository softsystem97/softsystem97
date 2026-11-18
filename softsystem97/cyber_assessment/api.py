"""Opt-in cyber intake on the same customer Issue bridge as the existing portal."""

import frappe

from .catalog import TIERS, build_ticket, request_payload, required_text


def _enabled():
    config = frappe.conf.get("ss97_cyber_assessment")
    if not isinstance(config, dict) or config.get("enabled") is not True:
        frappe.throw("Service en préparation : réception des demandes non activée.", frappe.PermissionError)


def _manager():
    user = frappe.session.user
    if (not user or user == "Guest"
            or not frappe.db.get_value("User", user, "enabled")
            or "System Manager" not in frappe.get_roles(user)):
        frappe.throw("Supervision réservée à la direction.", frappe.PermissionError)


@frappe.whitelist(allow_guest=True, methods=["GET"])
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
    from softsystem97.technician_exams.readiness import MAX_ACTIVE_BANK_SIZE, audit_bank
    from softsystem97.technician_exams.rules import TRACKS as EXAM_TRACKS
    tech = frappe.conf.get("ss97_tech_os") or {}
    exams = frappe.conf.get("ss97_technician_exams") or {}
    mail = frappe.conf.get("ss97_tech_email_notifications") or {}
    bridge = frappe.conf.get("ss97_ticket_bridge") or {}
    cyber = frappe.conf.get("ss97_cyber_assessment") or {}
    question_doctype = bool(frappe.db.exists("DocType", "SS97 Technician Exam Question"))
    technical_doctypes = ("SS97 Technician Profile", "SS97 Technician Mission",
                          "SS97 Technician OS Event", "SS97 Technician Document",
                          "SS97 Technician Notice", "SS97 Technician Settlement")
    tech_schema_ready = all(frappe.db.exists("DocType", name) for name in technical_doctypes)
    exam_schema_ready = question_doctype and bool(frappe.db.exists("DocType", "SS97 Technician Exam Attempt"))
    def bank_audit(track):
        if not question_doctype:
            return audit_bank([], EXAM_TRACKS[track].question_count)
        filters = {"track": track, "is_active": 1}
        try:
            total = frappe.db.count("SS97 Technician Exam Question", filters)
            rows = frappe.get_all(
                "SS97 Technician Exam Question", filters=filters,
                fields=["prompt", "options_json", "correct_option", "category"],
                limit_page_length=MAX_ACTIVE_BANK_SIZE + 1,
            )
            return audit_bank(rows, EXAM_TRACKS[track].question_count, total=total)
        except Exception:
            # An inaccessible or incomplete bank must not look deployable;
            # internal exceptions and private answers never reach the browser.
            return {"active_count": 0, "invalid_count": 0,
                    "duplicate_count": 0, "ready": False, "unavailable": True}
    audits = {track: bank_audit(track) for track in EXAM_TRACKS}
    return {"tech_os_enabled": isinstance(tech, dict) and tech.get("enabled") is True,
            "technician_schema_ready": tech_schema_ready,
            "exam_schema_ready": exam_schema_ready,
            "exams_enabled": isinstance(exams, dict) and exams.get("enabled") is True,
            "technician_email_enabled": isinstance(mail, dict) and mail.get("enabled") is True,
            "ticket_bridge_enabled": (isinstance(bridge, dict)
                                      and bridge.get("enabled") is True),
            "ticket_email_enabled": (isinstance(bridge, dict)
                                     and bridge.get("email_enabled") is True),
            "cyber_intake_enabled": (isinstance(cyber, dict)
                                    and cyber.get("enabled") is True),
            "client_notification_doctype": bool(frappe.db.exists("DocType", "SS97 Client Notification")),
            "n2_question_count": audits["L2"]["active_count"],
            "n3_question_count": audits["BANK"]["active_count"],
            "n4_question_count": audits["CYBER"]["active_count"],
            "question_bank_audit": audits,
            "question_banks_ready": all(result["ready"] for result in audits.values()),
            "stripe_connect_transfers_enabled": False}
