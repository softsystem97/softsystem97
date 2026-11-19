"""Read-only agenda for the currently authenticated SS97 technician.

Only server-assigned Issue appointments are returned. The caller cannot pass a
technician, ticket, customer, or arbitrary query to expand the result set.
"""

import frappe

from .technician_access import my_technician_access


def _agenda_rows(user):
    """A configured technician link is the agenda's ownership boundary."""
    if not frappe.db.table_exists("Issue"):
        return []
    meta = frappe.get_meta("Issue")
    if not all(meta.has_field(field) for field in (
        "ss97_technician", "ss97_appointment_on", "subject", "status", "priority"
    )):
        return []
    return frappe.db.sql(
        """SELECT name, subject, status, priority, ss97_appointment_on AS starts_at
             FROM `tabIssue`
            WHERE ss97_technician = %s
              AND ss97_appointment_on IS NOT NULL
            ORDER BY ss97_appointment_on ASC, name ASC
            LIMIT 100""",
        (user,),
        as_dict=True,
    )


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_my_agenda():
    """Return scheduled interventions for the session's active technician only."""
    access = my_technician_access()
    if not (access.get("authenticated") and
            (access.get("isTechnician") or access.get("isAdmin"))):
        frappe.throw("Accès technicien actif requis.", frappe.PermissionError)
    user = frappe.session.user
    # Never trust caller-supplied user filters or expose other people's entries.
    entries = [{
        "ticket": row["name"],
        "subject": row.get("subject") or "Intervention",
        "status": row.get("status") or "",
        "priority": row.get("priority") or "",
        "starts_at": str(row["starts_at"]),
    } for row in _agenda_rows(user)]
    return {"entries": entries, "count": len(entries)}
