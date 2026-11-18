"""Opt-in technician lifecycle and human-approved missions for Frappe v16.

No guest mutations, role auto-grant, e-signature, file uploads, payment initiation
or remote desktop commands. All Frappe documents are admin-read-only; every
portal endpoint enforces authorization again before ignore_permissions writes.
"""

from uuid import uuid4

import frappe
from frappe.utils import now_datetime

from .rules import (
    SENSITIVE_TRACKS, TRACKS, TRACK_ROLES, exact_track_role, fee_eur,
    next_mission_state, next_profile_state, reference, short_note, track_settings,
)


PROFILE = "SS97 Technician Profile"
MISSION = "SS97 Technician Mission"
EVENT = "SS97 Technician OS Event"
EXAM_ATTEMPT = "SS97 Technician Exam Attempt"
SYSTEM_ROLE = "System Manager"
CANDIDATE_ROLE = "Candidat SS97"


def _enabled():
    config = frappe.conf.get("ss97_tech_os") or {}
    if not isinstance(config, dict) or config.get("enabled") is not True:
        frappe.throw("SS97 TECH OS non activé.", frappe.PermissionError)
    for table in (PROFILE, MISSION, EVENT):
        if not frappe.db.table_exists(table):
            frappe.throw("Migration SS97 TECH OS manquante.", frappe.PermissionError)


def _user():
    user = frappe.session.user
    if not user or user == "Guest" or not frappe.db.get_value("User", user, "enabled"):
        frappe.throw("Compte actif requis.", frappe.PermissionError)
    return user


def _manager():
    user = _user()
    if SYSTEM_ROLE not in frappe.get_roles(user):
        frappe.throw("Responsable SS97 requis.", frappe.PermissionError)
    return user


def _profile_for_user(user, lock=False):
    name = frappe.db.get_value(PROFILE, {"candidate_user": user}, "name")
    if not name:
        return None
    return frappe.get_doc(PROFILE, name, for_update=lock)


def _profile_by_id(profile_id, lock=False):
    if not isinstance(profile_id, str) or len(profile_id) != 36:
        frappe.throw("Profil invalide.", frappe.PermissionError)
    if not frappe.db.exists(PROFILE, profile_id):
        frappe.throw("Profil introuvable.", frappe.PermissionError)
    return frappe.get_doc(PROFILE, profile_id, for_update=lock)


def _mission_by_id(mission_id, lock=False):
    if not isinstance(mission_id, str) or len(mission_id) != 36:
        frappe.throw("Mission invalide.", frappe.PermissionError)
    if not frappe.db.exists(MISSION, mission_id):
        frappe.throw("Mission introuvable.", frappe.PermissionError)
    return frappe.get_doc(MISSION, mission_id, for_update=lock)


def _log(entity_type, entity_id, action, actor):
    frappe.get_doc({
        "doctype": EVENT, "event_id": str(uuid4()),
        "entity_type": entity_type, "entity_id": entity_id,
        "action": action, "actor": actor, "occurred_at": now_datetime(),
    }).insert(ignore_permissions=True)


def _my_active_profile():
    user = _user()
    profile = _profile_for_user(user)
    if not profile or profile.state != "ACTIVE" or profile.engagement != "FREELANCE":
        frappe.throw("Habilitation freelance non active.", frappe.PermissionError)
    if not exact_track_role(frappe.get_roles(user), profile.track):
        frappe.throw("Rôles de spécialité incohérents ou révoqués.", frappe.PermissionError)
    return profile


def _profile_view(profile):
    # Never expose signed references, verification evidence, business IDs or RIB.
    return {"profile_id": profile.name, "track": profile.track,
            "track_label": track_settings(profile.track)["label"],
            "state": profile.state, "engagement": profile.engagement}


def _mission_view(mission, as_client=False):
    result = {"mission_id": mission.name, "ticket_name": mission.ticket_name,
              "track": mission.track, "state": mission.state}
    if not as_client:
        # Technician's remuneration is confidential and never client-facing.
        result["offered_fee_eur"] = str(mission.offered_fee_eur)
        result["payment_status"] = "NOT_SCHEDULED"
        result["route_instructions"] = mission.route_instructions or ""
    if mission.state in ("REPORT_SUBMITTED", "CLIENT_ACCEPTED", "DISPUTED"):
        result["report_summary"] = mission.report_summary or ""
    return result


def _authorized_ticket(mission, audience):
    # Reuses the authoritative ticket bridge. A matching email/ToDo alone is
    # never sufficient to authorize a technician or client.
    from softsystem97.integrations.ticket_bridge import policy

    if not frappe.db.exists("Issue", mission.ticket_name):
        frappe.throw("Ticket indisponible.", frappe.PermissionError)
    ticket = frappe.get_doc("Issue", mission.ticket_name)
    if not ticket.customer or ticket.customer != mission.customer:
        frappe.throw("Client du ticket incohérent.", frappe.PermissionError)
    policy.authorize(ticket, audience)
    return ticket


@frappe.whitelist(methods=["POST"])
def apply(track):
    """An invited candidate selects a track; selection grants no worker role."""
    _enabled()
    user = _user()
    roles = set(frappe.get_roles(user))
    if (CANDIDATE_ROLE not in roles or roles & TRACK_ROLES
            or SYSTEM_ROLE in roles or "Customer" in roles):
        frappe.throw("Compte candidat SS97 distinct requis.", frappe.PermissionError)
    try:
        track_settings(track)
    except ValueError as exc:
        frappe.throw(str(exc), frappe.PermissionError)
    # Serialize competing POSTs and prevent duplicate applications.
    if not frappe.db.sql("SELECT name FROM `tabUser` WHERE name=%s FOR UPDATE", (user,)):
        frappe.throw("Candidat introuvable.", frappe.PermissionError)
    if _profile_for_user(user):
        frappe.throw("Une candidature existe déjà pour ce compte.", frappe.PermissionError)
    profile = frappe.get_doc({
        "doctype": PROFILE, "profile_id": str(uuid4()),
        "candidate_user": user, "track": track, "state": "APPLIED",
        "engagement": "FREELANCE", "applied_at": now_datetime(),
    }).insert(ignore_permissions=True)
    _log("PROFILE", profile.name, "APPLIED", user)
    return _profile_view(profile)


@frappe.whitelist(methods=["GET"])
def get_my_workspace():
    _enabled()
    user = _user()
    profile = _profile_for_user(user)
    if not profile:
        if CANDIDATE_ROLE not in frappe.get_roles(user):
            frappe.throw("Candidature ou habilitation requise.", frappe.PermissionError)
        return {"profile": None, "tracks": [
            {"code": code, "label": item["label"]} for code, item in TRACKS.items()
        ], "missions": []}
    data = {"profile": _profile_view(profile), "missions": []}
    if profile.state != "ACTIVE":
        if user != profile.candidate_user:
            frappe.throw("Profil inaccessible.", frappe.PermissionError)
        return data
    _my_active_profile()
    rows = frappe.get_all(MISSION, filters={"technician": user, "track": profile.track},
                          fields=["name"], order_by="creation desc", limit_page_length=50)
    for row in rows:
        mission = _mission_by_id(row.name)
        # Revoked ticket assignment removes a mission from the worker view.
        try:
            _authorized_ticket(mission, "technician")
        except frappe.PermissionError:
            continue
        data["missions"].append(_mission_view(mission))
    return data


@frappe.whitelist(methods=["POST"])
def review_profile(profile_id, state, evidence_reference=""):
    """Human review only. The portal cannot sign contracts or verify IDs itself."""
    _enabled()
    reviewer = _manager()
    profile = _profile_by_id(profile_id, lock=True)
    if reviewer == profile.candidate_user:
        frappe.throw("Auto-validation interdite.", frappe.PermissionError)
    if profile.engagement != "FREELANCE" or not next_profile_state(profile.state, state):
        frappe.throw("Transition du dossier interdite.", frappe.PermissionError)
    if state == "EXAM_VALIDATED":
        if not frappe.db.table_exists(EXAM_ATTEMPT) or not frappe.db.exists(EXAM_ATTEMPT, {
            "candidate_user": profile.candidate_user, "track": profile.track, "state": "PASSED",
        }):
            frappe.throw("Examen de la filière non validé.", frappe.PermissionError)
    if state == "DOCUMENTS_VALIDATED":
        try:
            profile.verification_reference = reference(evidence_reference, "Preuve de vérification")
        except ValueError as exc:
            frappe.throw(str(exc), frappe.PermissionError)
        profile.documents_validated_by = reviewer
    if state == "CONTRACT_SIGNED":
        try:
            profile.contract_reference = reference(evidence_reference, "Référence de signature")
        except ValueError as exc:
            frappe.throw(str(exc), frappe.PermissionError)
        profile.contract_signed_at = now_datetime()
    if state == "ACTIVE":
        if (not profile.verification_reference or not profile.contract_reference
                or not profile.contract_signed_at or not frappe.db.get_value(
                    "User", profile.candidate_user, "enabled")
                or not exact_track_role(frappe.get_roles(profile.candidate_user), profile.track)):
            frappe.throw("Contrat, contrôle et rôle N2/N3/N4 requis.", frappe.PermissionError)
        if profile.track in SENSITIVE_TRACKS and profile.documents_validated_by == reviewer:
            frappe.throw("Double validation indépendante requise pour N3/N4.", frappe.PermissionError)
        profile.activated_by = reviewer
    profile.state = state
    profile.save(ignore_permissions=True)
    _log("PROFILE", profile.name, state, reviewer)
    return _profile_view(profile)


@frappe.whitelist(methods=["POST"])
def offer_mission(ticket_name, technician_user, offered_fee_eur,
                  route_instructions, authorization_reference=""):
    """Only human coordinators can issue an offer, and only on an approved Issue assignment."""
    _enabled()
    coordinator = _manager()
    if coordinator == technician_user:
        frappe.throw("Un responsable ne peut pas se proposer sa propre mission.", frappe.PermissionError)
    from softsystem97.integrations.ticket_bridge import policy

    policy.settings()
    if (not isinstance(ticket_name, str) or len(ticket_name) > 140
            or not isinstance(technician_user, str) or len(technician_user) > 140):
        frappe.throw("Ticket ou destinataire invalide.", frappe.PermissionError)
    if not frappe.db.sql("SELECT name FROM `tabIssue` WHERE name=%s FOR UPDATE", (ticket_name,)):
        frappe.throw("Ticket introuvable.", frappe.PermissionError)
    ticket = frappe.get_doc("Issue", ticket_name)
    if ticket.status == "Closed" or not ticket.customer or not ticket.raised_by:
        frappe.throw("Ticket client non disponible.", frappe.PermissionError)
    if not policy.assigned(ticket.name, technician_user):
        frappe.throw("Affectation native du ticket non autorisée.", frappe.PermissionError)
    profile = _profile_for_user(technician_user)
    if (not profile or profile.state != "ACTIVE" or profile.engagement != "FREELANCE"
            or not exact_track_role(frappe.get_roles(technician_user), profile.track)):
        frappe.throw("Technicien freelance non habilité dans cette spécialité.", frappe.PermissionError)
    if frappe.db.exists(MISSION, {"ticket_name": ticket_name, "technician": technician_user}):
        frappe.throw("Mission déjà attribuée pour ce ticket et ce technicien.", frappe.PermissionError)
    try:
        amount = fee_eur(offered_fee_eur)
        route = short_note(route_instructions)
        authorization = (reference(authorization_reference, "Autorisation sensible")
                         if profile.track in SENSITIVE_TRACKS else "")
    except ValueError as exc:
        frappe.throw(str(exc), frappe.PermissionError)
    state = "PENDING_APPROVAL" if profile.track in SENSITIVE_TRACKS else "OFFERED"
    mission = frappe.get_doc({
        "doctype": MISSION, "mission_id": str(uuid4()),
        "ticket_name": ticket.name, "customer": ticket.customer,
        "technician": technician_user, "track": profile.track, "state": state,
        "offered_fee_eur": amount, "currency": "EUR",
        "route_instructions": route, "authorization_reference": authorization,
        "created_by_user": coordinator,
    }).insert(ignore_permissions=True)
    _log("MISSION", mission.name, state, coordinator)
    return _mission_view(mission)


@frappe.whitelist(methods=["POST"])
def approve_sensitive_mission(mission_id):
    _enabled()
    approver = _manager()
    mission = _mission_by_id(mission_id, lock=True)
    if (mission.track not in SENSITIVE_TRACKS or mission.state != "PENDING_APPROVAL"
            or mission.created_by_user == approver or mission.technician == approver
            or not mission.authorization_reference):
        frappe.throw("Deuxième validation ou autorisation manquante.", frappe.PermissionError)
    from softsystem97.integrations.ticket_bridge import policy
    policy.settings()
    if not policy.assigned(mission.ticket_name, mission.technician):
        frappe.throw("Affectation révoquée.", frappe.PermissionError)
    mission.approved_by = approver
    mission.state = "OFFERED"
    mission.save(ignore_permissions=True)
    _log("MISSION", mission.name, "OFFERED", approver)
    return _mission_view(mission)


@frappe.whitelist(methods=["POST"])
def transition_my_mission(mission_id, state, report_summary=""):
    _enabled()
    profile = _my_active_profile()
    mission = _mission_by_id(mission_id, lock=True)
    if (mission.technician != profile.candidate_user or mission.track != profile.track
            or state not in {"ACCEPTED", "DECLINED", "IN_PROGRESS", "REPORT_SUBMITTED"}
            or not next_mission_state(mission.state, state)):
        frappe.throw("Transition de mission interdite.", frappe.PermissionError)
    ticket = _authorized_ticket(mission, "technician")
    if ticket.status == "Closed":
        frappe.throw("Ticket client fermé.", frappe.PermissionError)
    if state == "REPORT_SUBMITTED":
        try:
            mission.report_summary = short_note(report_summary, maximum=4000)
        except ValueError as exc:
            frappe.throw(str(exc), frappe.PermissionError)
        mission.report_submitted_at = now_datetime()
    if state == "ACCEPTED":
        mission.accepted_at = now_datetime()
    mission.state = state
    mission.save(ignore_permissions=True)
    _log("MISSION", mission.name, state, profile.candidate_user)
    return _mission_view(mission)


@frappe.whitelist(methods=["POST"])
def review_client_report(mission_id, decision):
    _enabled()
    client_user = _user()
    mission = _mission_by_id(mission_id, lock=True)
    if (client_user == mission.technician
            or set(frappe.get_roles(client_user)) & TRACK_ROLES):
        frappe.throw("Un technicien ne peut pas valider son propre rapport.", frappe.PermissionError)
    if decision not in {"CLIENT_ACCEPTED", "DISPUTED"} or not next_mission_state(
        mission.state, decision
    ):
        frappe.throw("Validation client interdite.", frappe.PermissionError)
    ticket = _authorized_ticket(mission, "client")
    if ticket.status == "Closed":
        frappe.throw("Ticket fermé.", frappe.PermissionError)
    mission.state = decision
    if decision == "CLIENT_ACCEPTED":
        mission.client_accepted_at = now_datetime()
    mission.save(ignore_permissions=True)
    _log("MISSION", mission.name, decision, client_user)
    # Client approval does not generate or release a payout.
    return _mission_view(mission, as_client=True)


@frappe.whitelist(methods=["GET"])
def get_client_missions(ticket_name):
    _enabled()
    client_user = _user()
    if set(frappe.get_roles(client_user)) & TRACK_ROLES:
        frappe.throw("Compte client distinct requis.", frappe.PermissionError)
    from softsystem97.integrations.ticket_bridge import policy
    if not isinstance(ticket_name, str) or len(ticket_name) > 140 or not frappe.db.exists("Issue", ticket_name):
        frappe.throw("Ticket invalide.", frappe.PermissionError)
    ticket = frappe.get_doc("Issue", ticket_name)
    policy.authorize(ticket, "client")
    rows = frappe.get_all(MISSION, filters={"ticket_name": ticket.name, "customer": ticket.customer},
                          fields=["name"], limit_page_length=50)
    return {"missions": [_mission_view(_mission_by_id(row.name), as_client=True) for row in rows]}
