"""One fail-closed remote-assistance entitlement for all three SS97 tracks.

This is deliberately not a whitelisted API. A valid portal role or a ToDo
alone cannot authorize remote assistance. It requires the technician's active
freelance profile, exact specialist role, approved native Issue assignment,
and an IN_PROGRESS mission belonging to that same customer and specialty.
"""

import frappe

from softsystem97.integrations.ticket_bridge import policy
from softsystem97.technician_os import api as technician_os
from softsystem97.technician_os.rules import TRACKS, SENSITIVE_TRACKS, exact_track_role, track_settings

CONFLICTING_OPERATOR_ROLES = frozenset({
    "System Manager", "Accounts User", "Accounts Manager", "Bank Manager",
    "SS97 Administrator", "SS97 Admin",
})


def _deny():
    frappe.throw("Assistance indisponible pour cette mission ou cette habilitation.",
                 frappe.PermissionError)


def check_mission(ticket, technician, profile, mission):
    """Pure comparison; the caller must separately verify identity and assignment."""
    if (not mission or not profile or not ticket
            or mission.ticket_name != ticket.name
            or mission.customer != ticket.customer
            or mission.technician != technician
            or mission.track != profile.track
            or mission.state != "IN_PROGRESS"
            or not mission.accepted_at):
        return False
    if profile.track in SENSITIVE_TRACKS:
        return bool(
            mission.authorization_reference
            and mission.approved_by
            and mission.approved_by != mission.created_by_user
            and mission.approved_by != mission.technician
        )
    return True


def authorize_technician_ticket(ticket, technician=None):
    """Return (user, track) only for an approved active mission on this ticket.

    `technician` is for internal validation of an existing invitation. It is
    NEVER a browser argument; callers must obtain it from a stored session.
    """
    policy.settings()
    technician_os._enabled()
    user = technician if technician is not None else frappe.session.user
    if (not isinstance(user, str) or not user or user == "Guest"
            or not frappe.db.get_value("User", user, "enabled")
            or not ticket or ticket.status == "Closed"
            or not ticket.customer or not ticket.raised_by):
        _deny()

    profile = technician_os._profile_for_user(user)
    roles = set(frappe.get_roles(user))
    if (not profile or profile.candidate_user != user or profile.track not in TRACKS
            or profile.state != "ACTIVE" or profile.engagement != "FREELANCE"
            or roles & CONFLICTING_OPERATOR_ROLES
            or not exact_track_role(roles, profile.track)):
        _deny()
    expected_role = track_settings(profile.track)["role"]
    if not frappe.db.exists("Role", {"name": expected_role, "disabled": 0}):
        _deny()
    if (not policy.assigned(ticket.name, user)
            or policy.client_customer_for_user(ticket.raised_by) != ticket.customer):
        _deny()

    missions = frappe.get_all(
        technician_os.MISSION,
        filters={"ticket_name": ticket.name, "customer": ticket.customer,
                 "technician": user, "track": profile.track,
                 "state": "IN_PROGRESS"},
        fields=["name"], limit_page_length=2,
    )
    if len(missions) != 1:
        _deny()
    mission = frappe.get_doc(technician_os.MISSION, missions[0].name)
    if not check_mission(ticket, user, profile, mission):
        _deny()
    return user, profile.track
