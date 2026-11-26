"""API privee du cockpit N2 pilote."""

import frappe

from frappe.sessions import get_csrf_token
from . import api, policy, cockpit, payment_gate


def require_pilot():

    if not cockpit.enabled():
        frappe.throw(
            "Cockpit pilote indisponible.",
            frappe.PermissionError
        )

    return policy.technician()


@frappe.whitelist(methods=["GET"])
def tickets():

    require_pilot()

    return api.list_tickets(
        audience="technician"
    )


@frappe.whitelist(methods=["GET"])
def state(name):

    require_pilot()

    doc = api._issue(name)

    policy.authorize(doc, "technician")

    return {
        "ticket": doc.name,
        "subject": doc.subject,
        "status": doc.get("ss97_ticket_status"),
        "timer": doc.get("ss97_timer_status"),
        "work_seconds": int(
            doc.get("ss97_work_seconds") or 0
        ),
        "pause_seconds": int(
            doc.get("ss97_pause_seconds") or 0
        ),
        "paid": payment_gate.issue_has_verified_stripe_payment(
            doc.name
        ),
        "suspended": bool(
            doc.get("ss97_security_suspend")
        ),
        "modified": str(doc.modified),

        "active_seconds": cockpit.elapsed(
            doc.get("ss97_timer_resumed_on")
            if doc.get("ss97_timer_status") == "running"
            else doc.get("ss97_pause_started_on"),
            frappe.utils.now_datetime()
        ) if (
            (
                doc.get("ss97_timer_status") == "running"
                and doc.get("ss97_timer_resumed_on")
            )
            or (
                doc.get("ss97_timer_status") == "paused"
                and doc.get("ss97_pause_started_on")
            )
        ) else 0,
        "csrf_token": get_csrf_token()
    }


@frappe.whitelist(methods=["POST"])
def transition(name, action, expected_modified):

    require_pilot()

    if action not in ("start", "pause", "resume"):
        frappe.throw(
            "Action non autorisee.",
            frappe.PermissionError
        )

    return cockpit.execute(
        name,
        action,
        expected_modified
    )


@frappe.whitelist(methods=["POST"])
def complete(name, expected_modified, diagnostic, report, checklist):

    require_pilot()

    from . import cockpit_completion

    return cockpit_completion.execute(
        name, "complete", expected_modified,
        diagnostic=diagnostic,
        report=report,
        checklist=checklist
    )


@frappe.whitelist(methods=["POST"])
def submit_close(name, expected_modified):

    require_pilot()

    from . import cockpit_completion

    return cockpit_completion.execute(
        name, "submit_close", expected_modified
    )


@frappe.whitelist(methods=["POST"])
def admin_close(name, expected_modified):

    from . import cockpit_completion

    policy.dispatcher()

    return cockpit_completion.execute(
        name, "admin_close", expected_modified
    )


@frappe.whitelist(methods=["GET"])
def availability():
    """Availability for an authenticated technician only."""

    require_pilot()

    return {
        "enabled": True,
        "route": "/espace-technicien/cockpit-n2"
    }
