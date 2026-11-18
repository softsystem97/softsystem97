"""Opt-in technician lifecycle and human-approved missions for Frappe v16.

No guest mutations, role auto-grant, e-signature, file uploads, payment initiation
or remote desktop commands. All Frappe documents are admin-read-only; every
portal endpoint enforces authorization again before ignore_permissions writes.
"""

from uuid import uuid4

import frappe
from frappe.utils import now_datetime

from .documents import REQUIRED_DOCUMENTS, check_private_upload, safe_private_file_url
from .notices import stage_notice, _mail_enabled
from .training import course_for_track
from .rules import (
    SENSITIVE_TRACKS, TRACKS, TRACK_ROLES, exact_track_role, fee_eur,
    next_mission_state, next_profile_state, reference, short_note, track_settings,
)


PROFILE = "SS97 Technician Profile"
MISSION = "SS97 Technician Mission"
EVENT = "SS97 Technician OS Event"
DOCUMENT = "SS97 Technician Document"
NOTICE = "SS97 Technician Notice"
SETTLEMENT = "SS97 Technician Settlement"
EXAM_ATTEMPT = "SS97 Technician Exam Attempt"
SYSTEM_ROLE = "System Manager"
CANDIDATE_ROLE = "Candidat SS97"
SAFE_CANDIDATE_ROLES = frozenset({"All", "Guest", "Website User", CANDIDATE_ROLE})


def _enabled():
    config = frappe.conf.get("ss97_tech_os") or {}
    if not isinstance(config, dict) or config.get("enabled") is not True:
        frappe.throw("SS97 TECH OS non activé.", frappe.PermissionError)
    for table in (PROFILE, MISSION, EVENT, DOCUMENT, NOTICE, SETTLEMENT):
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


def _can_apply(user):
    """Self-service only for ordinary website accounts, never ERPNext clients/staff."""
    roles = set(frappe.get_roles(user))
    return (frappe.db.get_value("User", user, "user_type") == "Website User"
            and roles <= SAFE_CANDIDATE_ROLES)


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
    event_id = str(uuid4())
    frappe.get_doc({
        "doctype": EVENT, "event_id": event_id,
        "entity_type": entity_type, "entity_id": entity_id,
        "action": action, "actor": actor, "occurred_at": now_datetime(),
    }).insert(ignore_permissions=True)
    return event_id


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


def _documents_for_profile(profile):
    rows = frappe.get_all(
        DOCUMENT, filters={"profile": profile.name, "candidate_user": profile.candidate_user},
        fields=["category", "state"], limit_page_length=10,
    )
    states = {item.category: item.state for item in rows}
    return [{"category": category, "label": label,
             "state": states.get(category, "MISSING")}
            for category, label in REQUIRED_DOCUMENTS.items()]


def _private_document_still_valid(document, candidate_user):
    """Fail closed if an uploaded credential was removed or made public later."""
    if document.candidate_user != candidate_user or not document.file:
        return False
    file_data = frappe.db.get_value(
        "File", document.file,
        ["name", "owner", "is_private", "file_url", "file_name", "file_size",
         "attached_to_doctype", "attached_to_name"], as_dict=True,
    )
    try:
        check_private_upload(file_data, candidate_user)
    except (ValueError, TypeError):
        return False
    return True


def _documents_verified(profile):
    documents = frappe.get_all(
        DOCUMENT, filters={"profile": profile.name, "candidate_user": profile.candidate_user},
        fields=["category", "candidate_user", "state", "file"], limit_page_length=10,
    )
    verified = {}
    for document in documents:
        if document.category not in REQUIRED_DOCUMENTS or document.category in verified:
            return False
        verified[document.category] = (
            document.state == "VERIFIED"
            and _private_document_still_valid(document, profile.candidate_user)
        )
    return set(verified) == set(REQUIRED_DOCUMENTS) and all(verified.values())


def _mission_view(mission, as_client=False):
    result = {"mission_id": mission.name, "ticket_name": mission.ticket_name,
              "track": mission.track, "state": mission.state}
    if not as_client:
        # Technician's remuneration is confidential and never client-facing.
        result["offered_fee_eur"] = str(mission.offered_fee_eur)
        result["payment_status"] = "NOT_SCHEDULED"
        result["route_instructions"] = mission.route_instructions or ""
    if mission.state in ("REPORT_SUBMITTED", "CLIENT_ACCEPTED", "DISPUTED", "REWORK_PENDING_APPROVAL"):
        result["report_summary"] = mission.report_summary or ""
    if mission.state in ("DISPUTED", "REWORK_PENDING_APPROVAL"):
        result["dispute_reason"] = mission.dispute_reason or ""
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
    """A signed-in website user selects one track; selection grants no role."""
    _enabled()
    user = _user()
    if not _can_apply(user):
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
    event_id = _log("PROFILE", profile.name, "APPLIED", user)
    stage_notice(profile, "APPLIED", event_id)
    return _profile_view(profile)


@frappe.whitelist(methods=["POST"])
def submit_private_document(category, file_id):
    """Link an already-private, candidate-owned Frappe File to this dossier.

    Bytes are uploaded through Frappe's native /api/method/upload_file route.
    No document bytes or URLs are returned by this endpoint.
    """
    _enabled()
    user = _user()
    profile = _profile_for_user(user, lock=True)
    if (not profile or profile.state not in {"APPLIED", "IN_REVIEW", "EXAM_VALIDATED"}
            or category not in REQUIRED_DOCUMENTS):
        frappe.throw("Dossier ou type de pièce indisponible.", frappe.PermissionError)
    if not isinstance(file_id, str) or len(file_id) > 140:
        frappe.throw("Fichier invalide.", frappe.PermissionError)
    file_data = frappe.db.get_value(
        "File", file_id,
        ["name", "owner", "is_private", "file_url", "file_name", "file_size",
         "attached_to_doctype", "attached_to_name"], as_dict=True,
    )
    try:
        check_private_upload(file_data, user)
    except ValueError as exc:
        frappe.throw(str(exc), frappe.PermissionError)
    # Profile row lock serializes two simultaneous submissions for one category.
    existing = frappe.db.get_value(
        DOCUMENT, {"profile": profile.name, "category": category}, "name"
    )
    if existing:
        doc = frappe.get_doc(DOCUMENT, existing, for_update=True)
        if doc.state != "REJECTED":
            frappe.throw("Pièce déjà soumise : attendez le contrôle.", frappe.PermissionError)
        doc.file = file_id
        doc.state = "SUBMITTED"
        doc.reviewed_by = ""
        doc.reviewed_at = None
        doc.verification_reference = ""
        doc.submitted_at = now_datetime()
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc({
            "doctype": DOCUMENT, "document_id": str(uuid4()),
            "profile": profile.name, "candidate_user": user,
            "category": category, "file": file_id,
            "state": "SUBMITTED", "submitted_at": now_datetime(),
        }).insert(ignore_permissions=True)
    _log("PROFILE", profile.name, f"DOCUMENT_{category}_SUBMITTED", user)
    return {"category": category, "state": doc.state}


@frappe.whitelist(methods=["GET"])
def get_admin_documents(profile_id):
    """Only a System Manager receives private download links for review."""
    _enabled()
    _manager()
    profile = _profile_by_id(profile_id)
    rows = frappe.get_all(
        DOCUMENT, filters={"profile": profile.name},
        fields=["name", "candidate_user", "category", "state", "file"],
        limit_page_length=10,
    )
    result = []
    for row in rows:
        if row.candidate_user != profile.candidate_user:
            continue
        file_data = frappe.db.get_value(
            "File", row.file, ["is_private", "file_url", "file_name", "owner"], as_dict=True,
        )
        # Even staff cannot get an unverified public/external URL from this API.
        if (not file_data or int(file_data.is_private or 0) != 1
                or file_data.owner != profile.candidate_user
                or not safe_private_file_url(file_data.file_url)):
            continue
        result.append({"document_id": row.name, "category": row.category,
                       "state": row.state, "file_name": file_data.file_name,
                       "private_url": file_data.file_url})
    return {"documents": result}


@frappe.whitelist(methods=["POST"])
def review_document(document_id, decision, evidence_reference=""):
    """Independent, explicit human verification; never AI-verified or auto-approved."""
    _enabled()
    reviewer = _manager()
    if not isinstance(document_id, str) or len(document_id) != 36:
        frappe.throw("Pièce invalide.", frappe.PermissionError)
    # Always lock profile first: same order as submit_private_document.
    profile_id = frappe.db.get_value(DOCUMENT, document_id, "profile")
    if not profile_id:
        frappe.throw("Pièce introuvable.", frappe.PermissionError)
    profile = _profile_by_id(profile_id, lock=True)
    doc = frappe.get_doc(DOCUMENT, document_id, for_update=True)
    if (reviewer == doc.candidate_user or doc.state != "SUBMITTED"
            or decision not in {"VERIFIED", "REJECTED"}):
        frappe.throw("Contrôle documentaire interdit.", frappe.PermissionError)
    if (profile.candidate_user != doc.candidate_user
            or profile.state not in {"APPLIED", "IN_REVIEW", "EXAM_VALIDATED"}):
        frappe.throw("Dossier documentaire non vérifiable.", frappe.PermissionError)
    try:
        proof = reference(evidence_reference, "Preuve du contrôle humain")
    except ValueError as exc:
        frappe.throw(str(exc), frappe.PermissionError)
    if decision == "VERIFIED" and not _private_document_still_valid(doc, profile.candidate_user):
        frappe.throw("Justificatif devenu inaccessible ou non privé.", frappe.PermissionError)
    doc.state = decision
    doc.reviewed_by = reviewer
    doc.reviewed_at = now_datetime()
    doc.verification_reference = proof
    doc.save(ignore_permissions=True)
    _log("PROFILE", profile.name, f"DOCUMENT_{doc.category}_{decision}", reviewer)
    return {"category": doc.category, "state": decision}


@frappe.whitelist(methods=["GET"])
def get_my_workspace():
    _enabled()
    user = _user()
    profile = _profile_for_user(user)
    if not profile:
        if not _can_apply(user):
            frappe.throw("Candidature ou habilitation requise.", frappe.PermissionError)
        return {"profile": None, "tracks": [
            {"code": code, "label": item["label"]} for code, item in TRACKS.items()
        ], "missions": []}
    data = {"profile": _profile_view(profile), "training": course_for_track(profile.track),
            "missions": [],
            "documents": _documents_for_profile(profile)}
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
        view = _mission_view(mission)
        settlement_state = frappe.db.get_value(
            SETTLEMENT, {"mission": mission.name}, "state"
        )
        if settlement_state:
            view["payment_status"] = "APPROVAL_ONLY_" + settlement_state
        data["missions"].append(view)
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
        if not _documents_verified(profile):
            frappe.throw("Pièce d'identité et diplôme vérifiés requis.", frappe.PermissionError)
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
                or not _documents_verified(profile)
                or not exact_track_role(frappe.get_roles(profile.candidate_user), profile.track)):
            frappe.throw("Contrat, pièces privées et rôle N2/N3/N4 requis.", frappe.PermissionError)
        if profile.track in SENSITIVE_TRACKS and profile.documents_validated_by == reviewer:
            frappe.throw("Double validation indépendante requise pour N3/N4.", frappe.PermissionError)
        if profile.track in SENSITIVE_TRACKS and frappe.db.exists(DOCUMENT, {
                "profile": profile.name, "reviewed_by": reviewer, "state": "VERIFIED"}):
            frappe.throw("Le validateur final N3/N4 doit être distinct du contrôleur des pièces.", frappe.PermissionError)
        profile.activated_by = reviewer
    profile.state = state
    profile.save(ignore_permissions=True)
    event_id = _log("PROFILE", profile.name, state, reviewer)
    stage_notice(profile, state, event_id)
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
    ticket = _active_assignment_ticket(mission)
    if approver == ticket.raised_by:
        frappe.throw("Le client ne peut pas approuver sa propre mission.", frappe.PermissionError)
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
def review_client_report(mission_id, decision, dispute_reason=""):
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
    if decision == "DISPUTED":
        try:
            mission.dispute_reason = short_note(dispute_reason, maximum=500)
        except ValueError as exc:
            frappe.throw(str(exc), frappe.PermissionError)
    mission.state = decision
    if decision == "CLIENT_ACCEPTED":
        mission.client_accepted_at = now_datetime()
    mission.save(ignore_permissions=True)
    _log("MISSION", mission.name, decision, client_user)
    # Client approval does not generate or release a payout.
    return _mission_view(mission, as_client=True)


def _active_assignment_ticket(mission):
    """Live assignment, customer and credential checks before sensitive work."""
    from softsystem97.integrations.ticket_bridge import policy

    policy.settings()
    if not frappe.db.exists("Issue", mission.ticket_name):
        frappe.throw("Ticket inexistant pour une reprise.", frappe.PermissionError)
    ticket = frappe.get_doc("Issue", mission.ticket_name)
    profile = _profile_for_user(mission.technician)
    if (ticket.status == "Closed" or not ticket.customer
            or ticket.customer != mission.customer
            or not policy.assigned(ticket.name, mission.technician)
            or not profile or profile.state != "ACTIVE"
            or profile.engagement != "FREELANCE" or profile.track != mission.track
            or not exact_track_role(frappe.get_roles(mission.technician), mission.track)):
        frappe.throw("Reprise interdite : ticket, affectation ou habilitation à vérifier.", frappe.PermissionError)
    return ticket


@frappe.whitelist(methods=["POST"])
def request_dispute_rework(mission_id, evidence_reference, authorization_reference=""):
    """Manager may request corrected work; N3/N4 await independent approval."""
    _enabled()
    manager = _manager()
    mission = _mission_by_id(mission_id, lock=True)
    if mission.state != "DISPUTED":
        frappe.throw("Seule une mission contestée peut être reprise.", frappe.PermissionError)
    ticket = _active_assignment_ticket(mission)
    if manager in {mission.technician, ticket.raised_by}:
        frappe.throw("Contrôle indépendant obligatoire.", frappe.PermissionError)
    try:
        proof = reference(evidence_reference, "Décision motivée de reprise")
        mandate = (reference(authorization_reference, "Nouveau mandat écrit pour la reprise")
                   if mission.track in SENSITIVE_TRACKS else "")
    except ValueError as exc:
        frappe.throw(str(exc), frappe.PermissionError)
    mission.rework_requested_by = manager
    mission.rework_requested_at = now_datetime()
    mission.rework_decision_reference = proof
    mission.rework_authorization_reference = mandate
    mission.rework_approved_by = ""
    mission.rework_approved_at = None
    if mission.track in SENSITIVE_TRACKS:
        mission.state = "REWORK_PENDING_APPROVAL"
    else:
        mission.state = "IN_PROGRESS"
        mission.rework_count = int(mission.rework_count or 0) + 1
        mission.report_summary = ""
        mission.report_submitted_at = None
    mission.save(ignore_permissions=True)
    _log("MISSION", mission.name, "REWORK_REQUESTED", manager)
    return _mission_view(mission)


@frappe.whitelist(methods=["POST"])
def approve_sensitive_rework(mission_id):
    """A second manager validates a fresh written mandate before N3/N4 resume."""
    _enabled()
    manager = _manager()
    mission = _mission_by_id(mission_id, lock=True)
    if (mission.state != "REWORK_PENDING_APPROVAL"
            or mission.track not in SENSITIVE_TRACKS
            or not mission.rework_authorization_reference
            or manager in {mission.rework_requested_by, mission.technician}):
        frappe.throw("Deuxième contrôle de reprise insuffisant.", frappe.PermissionError)
    ticket = _active_assignment_ticket(mission)
    if manager == ticket.raised_by:
        frappe.throw("Le client ne peut pas approuver sa propre reprise.", frappe.PermissionError)
    mission.rework_approved_by = manager
    mission.rework_approved_at = now_datetime()
    mission.rework_count = int(mission.rework_count or 0) + 1
    mission.report_summary = ""
    mission.report_submitted_at = None
    mission.state = "IN_PROGRESS"
    mission.save(ignore_permissions=True)
    _log("MISSION", mission.name, "SENSITIVE_REWORK_APPROVED", manager)
    return _mission_view(mission)


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


@frappe.whitelist(methods=["GET"])
def get_admin_overview():
    """Minimal supervisor view: no ID images, signature evidence, bank data or keys."""
    _enabled()
    _manager()
    profiles = frappe.get_all(PROFILE, fields=["name", "candidate_user", "track", "state",
                                              "engagement"], order_by="creation desc",
                              limit_page_length=100)
    missions = frappe.get_all(MISSION, fields=["name", "ticket_name", "technician",
                                              "track", "state", "created_by_user",
                                              "dispute_reason"],
                              order_by="creation desc", limit_page_length=100)
    settlements = frappe.get_all(SETTLEMENT, fields=["name", "mission", "state",
                                                  "technician", "amount_eur"],
                                 order_by="creation desc", limit_page_length=100)
    notices = frappe.get_all(NOTICE, fields=["state"], limit_page_length=1000)
    latest_notices = frappe.get_all(
        NOTICE, fields=["name", "kind", "state", "candidate_user"],
        order_by="creation desc", limit_page_length=50,
    )
    return {"profiles": [dict(row) for row in profiles],
            "missions": [dict(row) for row in missions],
            "settlements": [dict(row) for row in settlements],
            "notice_counts": {state: sum(1 for row in notices if row.state == state)
                              for state in ("HELD", "PENDING", "QUEUED", "ERROR")},
            "latest_notices": [dict(row) for row in latest_notices],
            "email_enabled": _mail_enabled(),
            "limit": 100,
            "notice": "Validation comptable uniquement : aucun virement bancaire dans ce module."}


@frappe.whitelist(methods=["POST"])
def retry_candidate_notice(notice_id):
    """A manager may release a held/failed notice only after SMTP validation."""
    _enabled()
    manager = _manager()
    if not _mail_enabled():
        frappe.throw("Envoi des courriels non activé.", frappe.PermissionError)
    if not isinstance(notice_id, str) or len(notice_id) != 36:
        frappe.throw("Notification invalide.", frappe.PermissionError)
    notice = frappe.get_doc(NOTICE, notice_id, for_update=True)
    if notice.state not in {"HELD", "ERROR"}:
        frappe.throw("Notification non relançable.", frappe.PermissionError)
    notice.state = "PENDING"
    notice.save(ignore_permissions=True)
    _log("PROFILE", notice.profile, "NOTIFICATION_RETRY", manager)
    frappe.enqueue("softsystem97.technician_os.notices.deliver_notice", queue="short",
                   enqueue_after_commit=True, notice_id=notice.name)
    return {"notice_id": notice.name, "state": "PENDING",
            "info": "Envoi à traiter par la file Frappe, pas encore livré."}


@frappe.whitelist(methods=["POST"])
def prepare_settlement(mission_id):
    """A distinct financial dossier follows client acceptance, never a payout."""
    _enabled()
    manager = _manager()
    mission = _mission_by_id(mission_id, lock=True)
    if (mission.state != "CLIENT_ACCEPTED" or mission.technician == manager
            or not mission.client_accepted_at):
        frappe.throw("Mission non éligible à la vérification financière.", frappe.PermissionError)
    if frappe.db.exists(SETTLEMENT, {"mission": mission.name}):
        frappe.throw("Rémunération déjà préparée.", frappe.PermissionError)
    settlement = frappe.get_doc({
        "doctype": SETTLEMENT, "settlement_id": str(uuid4()),
        "mission": mission.name, "technician": mission.technician,
        "currency": "EUR", "amount_eur": mission.offered_fee_eur,
        "state": "REVIEW_REQUIRED", "prepared_by": manager,
    }).insert(ignore_permissions=True)
    _log("MISSION", mission.name, "SETTLEMENT_REVIEW_REQUIRED", manager)
    return {"settlement_id": settlement.name, "state": settlement.state,
            "notice": "Aucun versement exécuté."}


@frappe.whitelist(methods=["POST"])
def approve_settlement(settlement_id, evidence_reference):
    """Second internal check; bank-transfer instructions are intentionally absent."""
    _enabled()
    manager = _manager()
    if not isinstance(settlement_id, str) or len(settlement_id) != 36:
        frappe.throw("Rémunération invalide.", frappe.PermissionError)
    mission_id = frappe.db.get_value(SETTLEMENT, settlement_id, "mission")
    if not mission_id:
        frappe.throw("Rémunération introuvable.", frappe.PermissionError)
    mission = _mission_by_id(mission_id, lock=True)
    settlement = frappe.get_doc(SETTLEMENT, settlement_id, for_update=True)
    if (settlement.state != "REVIEW_REQUIRED" or mission.state != "CLIENT_ACCEPTED"
            or settlement.technician != mission.technician
            or manager in {settlement.prepared_by, mission.technician, mission.created_by_user}):
        frappe.throw("Double contrôle financier insuffisant.", frappe.PermissionError)
    try:
        proof = reference(evidence_reference, "Preuve d'approbation financière")
    except ValueError as exc:
        frappe.throw(str(exc), frappe.PermissionError)
    settlement.state = "APPROVED"
    settlement.approved_by = manager
    settlement.approved_at = now_datetime()
    settlement.approval_reference = proof
    settlement.save(ignore_permissions=True)
    _log("MISSION", mission.name, "SETTLEMENT_APPROVED_NO_PAYOUT", manager)
    return {"settlement_id": settlement.name, "state": settlement.state,
            "notice": "Approbation interne seulement. Aucun paiement effectué."}


@frappe.whitelist(methods=["POST"])
def cancel_mission(mission_id, reason):
    """Stop an offer/intervention without altering the linked Issue or paying."""
    _enabled()
    manager = _manager()
    mission = _mission_by_id(mission_id, lock=True)
    if not next_mission_state(mission.state, "CANCELLED"):
        frappe.throw("Cette mission ne peut plus être annulée.", frappe.PermissionError)
    try:
        mission.cancellation_reason = short_note(reason, maximum=500)
    except ValueError as exc:
        frappe.throw(str(exc), frappe.PermissionError)
    mission.state = "CANCELLED"
    mission.save(ignore_permissions=True)
    _log("MISSION", mission.name, "CANCELLED", manager)
    return _mission_view(mission)
