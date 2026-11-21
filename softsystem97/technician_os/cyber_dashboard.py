"""Strictly scoped N4 cyber dashboard, reusing TECH OS authoritative permissions.

No active scan, secret access, account creation, role grant, financial settlement
or mission approval is possible from this read-only endpoint.
"""
import frappe

from softsystem97.technician_os.api import (
    _my_active_profile, _authorized_ticket, _mission_by_id, _profile_view,
    MISSION, _enabled,
)

ALLOWED_STATES = (
    "OFFERED", "ACCEPTED", "IN_PROGRESS", "REPORT_SUBMITTED",
    "CLIENT_ACCEPTED", "DISPUTED", "REWORK_PENDING_APPROVAL"
)


from .cyber_dashboard_rules import summarize


@frappe.whitelist(methods=["GET"])
def get_my_n4_dashboard():
    _enabled()
    profile = _my_active_profile()
    if profile.track != "CYBER" or profile.candidate_user != frappe.session.user:
        frappe.throw("Habilitation N4 active obligatoire.", frappe.PermissionError)

    rows = frappe.get_all(
        MISSION, filters={"technician": frappe.session.user, "track": "CYBER",
                          "state": ["in", ALLOWED_STATES]},
        fields=["name"], order_by="creation desc", limit_page_length=100,
    )
    missions = []
    eligible_tickets = set()
    for row in rows:
        mission = _mission_by_id(row.name)
        if (mission.track != "CYBER" or mission.technician != frappe.session.user
                or mission.state not in ALLOWED_STATES
                or not mission.authorization_reference or not mission.approved_by
                or mission.approved_by == mission.created_by_user
                or mission.approved_by == mission.technician):
            continue
        try:
            ticket = _authorized_ticket(mission, "technician")
        except frappe.PermissionError:
            continue
        if ticket.status == "Closed":
            continue
        missions.append({
            "mission_id": mission.name,
            "ticket_name": mission.ticket_name,
            "state": mission.state,
            "route_instructions": mission.route_instructions or "",
            "report_submitted": bool(mission.report_submitted_at),
            "has_written_mandate": True,
            "second_approval": True,
        })
        if mission.state in ("REPORT_SUBMITTED", "CLIENT_ACCEPTED"):
            eligible_tickets.add(mission.ticket_name)

    assessments = []
    if eligible_tickets and frappe.db.exists("DocType", "SS97 Cyber Assessment"):
        for row in frappe.get_all(
                "SS97 Cyber Assessment",
                filters={"ticket": ["in", sorted(eligible_tickets)]},
                fields=["name", "ticket", "organization", "tier", "state"],
                limit_page_length=100):
            # Review endpoint separately re-checks the sensitive mission,
            # mandate and active ticket grant at the time of every write.
            assessments.append({
                "name": row.name, "ticket": row.ticket,
                "organization": row.organization, "tier": row.tier,
                "state": row.state,
            })
    return {
        "profile": _profile_view(profile),
        "summary": summarize(missions),
        "missions": missions,
        "assessments": assessments,
        "review_url": "/ss97-cyber-review",
        "warning": "Aucune mission hors mandat ni aucun contrôle automatique du réseau n'est autorisé.",
    }
