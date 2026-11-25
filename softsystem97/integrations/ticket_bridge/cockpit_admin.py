"""Administration securisee du cockpit N2 pilote."""

import frappe

from frappe.sessions import get_csrf_token
from frappe.utils import strip_html
from . import api, policy, cockpit, cockpit_completion


def require_admin():

    if not cockpit.enabled():

        frappe.throw(
            "Pilote indisponible.",
            frappe.PermissionError
        )

    policy.dispatcher()


@frappe.whitelist(methods=["GET"])
def pending():

    require_admin()

    rows = frappe.get_list(
        "Issue",
        filters={
            "status": "Resolved",
            "ss97_ticket_status":
                cockpit_completion.PENDING
        },
        fields=[
            "name", "subject", "modified"
        ],
        order_by="modified desc",
        limit_page_length=50
    )

    return {"tickets": rows}


@frappe.whitelist(methods=["GET"])
def review(name):

    require_admin()

    doc = api._issue(name)

    doc.check_permission("read")

    if doc.ss97_ticket_status != cockpit_completion.PENDING:

        frappe.throw(
            "Ticket non soumis.",
            frappe.PermissionError
        )

    return {
        "ticket": doc.name,
        "subject": doc.subject,
        "technician": doc.ss97_technician,
        "diagnostic": doc.ss97_diagnostic,
        "report": strip_html(
            doc.ss97_intervention_report or ""
        ),
        "duration": doc.ss97_actual_duration_min,
        "modified": str(doc.modified),
        "csrf_token": get_csrf_token()
    }


@frappe.whitelist(methods=["POST"])
def close(name, expected_modified):

    require_admin()

    return cockpit_completion.execute(
        name,
        "admin_close",
        expected_modified
    )
