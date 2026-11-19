"""Revoke pending invitations when the Issue closes or assignments change."""

import frappe

from .api import SESSION, PENDING, _session, _transition


def _available():
    config = frappe.conf.get("ss97_remote_assist") or {}
    return (isinstance(config, dict) and config.get("enabled") is True
            and frappe.db.table_exists(SESSION))


def _end_pending(ticket_name, technician=None):
    filters = {"ticket_name": ticket_name, "state": ["in", list(PENDING)]}
    if technician:
        filters["technician"] = technician
    for row in frappe.get_all(SESSION, filters=filters,
                              fields=["name"], limit_page_length=200):
        session = _session(row.name, lock=True)
        if session.state in PENDING:
            _transition(session, "ENDED", "system")


def revoke_on_issue_close(doc, method=None):
    if not _available():
        return
    previous = doc.get_doc_before_save() if method != "on_trash" else None
    if (doc.status == "Closed" or (previous and (
            previous.customer != doc.customer or previous.raised_by != doc.raised_by))):
        _end_pending(doc.name)


def revoke_on_mission_change(doc, method=None):
    """End unconnected requests when an accepted mission is no longer active."""
    if _available() and doc.state != "IN_PROGRESS":
        _end_pending(doc.ticket_name, doc.technician)


def revoke_on_profile_change(doc, method=None):
    """Suspending/revoking a technician invalidates their pending invitations."""
    if not _available() or (doc.state == "ACTIVE" and doc.engagement == "FREELANCE"):
        return
    rows = frappe.get_all(SESSION, filters={"technician": doc.candidate_user,
        "state": ["in", list(PENDING)]}, fields=["ticket_name"], limit_page_length=200)
    for ticket_name in {row.ticket_name for row in rows}:
        _end_pending(ticket_name, doc.candidate_user)


def revoke_on_todo_change(doc, method=None):
    if not _available():
        return
    before = doc.get_doc_before_save() if method != "on_trash" else None
    tickets = set()
    for item in (doc, before):
        if item and item.reference_type == "Issue" and item.reference_name:
            tickets.add(item.reference_name)
    if not tickets:
        return
    from softsystem97.integrations.ticket_bridge import policy
    for ticket in tickets:
        rows = frappe.get_all(SESSION, filters={"ticket_name": ticket,
            "state": ["in", list(PENDING)]}, fields=["name", "technician"], limit_page_length=200)
        for row in rows:
            if method == "on_trash" and doc.reference_name == ticket and doc.allocated_to == row.technician:
                _end_pending(ticket, row.technician)
            elif not policy.assigned(ticket, row.technician):
                _end_pending(ticket, row.technician)
