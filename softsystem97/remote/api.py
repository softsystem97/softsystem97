"""SS97 Remote Assist V1.

This deliberately coordinates tickets and consent only. It never opens a remote
desktop, claims MeshCentral consent, or accepts a browser-supplied device ID.
All endpoints fail closed until an operator explicitly enables the pilot.
"""

from uuid import uuid4

import frappe
from frappe.utils import get_datetime, now_datetime

from softsystem97.integrations.ticket_bridge import historical, payment_gate, policy
from .logic import (
    ASSISTANCE_WINDOW_MINUTES, PENDING, TERMINAL, assistance_window_end,
    can_transition, code_digest, new_code, normalize_code,
)

SESSION = "SS97 Remote Session"
EVENT = "SS97 Remote Event"


def _settings():
    config = frappe.conf.get("ss97_remote_assist")
    if not isinstance(config, dict) or config.get("enabled") is not True:
        frappe.throw("Assistance à distance non activée.", frappe.PermissionError)
    # Reuse the already-reviewed ticket bridge's tenant / assignee permissions.
    policy.settings()
    secret = frappe.conf.get("encryption_key")
    if not isinstance(secret, str) or len(secret) < 32:
        frappe.throw("Clé de chiffrement du site manquante.", frappe.PermissionError)
    return secret


def _issue(name, lock=False):
    if not isinstance(name, str) or not name or len(name) > 140:
        frappe.throw("Ticket invalide.", frappe.PermissionError)
    if not frappe.db.exists("Issue", name):
        frappe.throw("Ticket inaccessible.", frappe.PermissionError)
    return frappe.get_doc("Issue", name, for_update=lock)


def _session(session_id, lock=False):
    if not isinstance(session_id, str) or not session_id or len(session_id) > 64:
        frappe.throw("Session invalide.", frappe.PermissionError)
    if not frappe.db.exists(SESSION, session_id):
        frappe.throw("Session inaccessible.", frappe.PermissionError)
    return frappe.get_doc(SESSION, session_id, for_update=lock)


def _authorized(session, audience):
    # Both the immutable session owner and the current ticket assignment count.
    ticket = _issue(session.ticket_name)
    user = policy.authorize(ticket, audience)
    if (ticket.customer != session.customer
            or (audience == "client" and (ticket.raised_by != session.client_user
                                              or user != session.client_user))
            or (audience == "technician" and user != session.technician)):
        frappe.throw("Session inaccessible.", frappe.PermissionError)
    return user


def _event(session, action, actor):
    frappe.get_doc({
        "doctype": EVENT,
        "event_id": str(uuid4()),
        "session": session.name,
        "event_type": action,
        "actor": actor,
        "occurred_at": now_datetime(),
    }).insert(ignore_permissions=True)


def _view(session):
    # Never return the code digest, MeshCentral credentials or device identifiers.
    return {
        "session_id": session.name,
        "ticket_name": session.ticket_name,
        "state": session.state,
        "technician": session.technician,
        "expires_at": str(session.expires_at),
        "consented_at": str(session.consented_at or ""),
        "ended_at": str(session.ended_at or ""),
        "assistance_window_minutes": ASSISTANCE_WINDOW_MINUTES,
        "engine_connected": False,
    }


def _expired(session):
    return session.state in PENDING and get_datetime(session.expires_at) <= now_datetime()


def _transition(session, state, actor):
    if not can_transition(session.state, state):
        frappe.throw("Transition de session interdite.", frappe.PermissionError)
    session.state = state
    if state == "CLIENT_READY":
        # The code is consumed when the correct customer joins, not merely
        # when a client later accepts or declines. It cannot be replayed.
        session.code_digest = None
    elif state == "CLIENT_APPROVED":
        session.consented_at = now_datetime()
    elif state in TERMINAL:
        session.ended_at = now_datetime()
        session.code_digest = None  # unique index permits multiple revoked codes
    session.save(ignore_permissions=True)
    _event(session, state, actor)
    return _view(session)


@frappe.whitelist(methods=["POST"])
def prepare_session(ticket_name):
    """Return the nine-digit code exactly once to the assigned technician."""
    secret = _settings()
    technician = policy.technician()
    ticket = _issue(ticket_name, lock=True)
    policy.authorize(ticket, "technician")
    if ticket.status == "Closed" or not ticket.customer or not ticket.raised_by:
        frappe.throw("Ticket non admissible.", frappe.PermissionError)
    if policy.client_customer_for_user(ticket.raised_by) != ticket.customer:
        frappe.throw("Client du ticket non vérifié.", frappe.PermissionError)
    payment_gate.require_paid_intervention(ticket.name, "intervention")
    historical.require_authorization("intervention", ticket, technician=technician)

    # The Issue row lock serializes simultaneous preparations for this ticket.
    pending = frappe.get_all(SESSION, filters={
        "ticket_name": ticket.name,
        "state": ["in", list(PENDING)],
        "expires_at": [">", now_datetime()],
    }, fields=["name"], limit_page_length=1)
    if pending:
        frappe.throw("Une assistance est déjà en attente pour ce ticket.", frappe.PermissionError)

    code = ""
    digest = ""
    for _ in range(10):
        code = new_code()
        digest = code_digest(code, secret)
        if not frappe.db.exists(SESSION, {"code_digest": digest}):
            break
    else:
        frappe.throw("Impossible de générer un code unique.")

    prepared_at = now_datetime()
    session = frappe.get_doc({
        "doctype": SESSION,
        "session_id": str(uuid4()),
        "ticket_name": ticket.name,
        "customer": ticket.customer,
        "client_user": ticket.raised_by,
        "technician": technician,
        "state": "CREATED",
        "code_digest": digest,
        "expires_at": assistance_window_end(prepared_at),
    }).insert(ignore_permissions=True)
    _event(session, "CREATED", technician)
    return {**_view(session), "join_code": code}


@frappe.whitelist(methods=["POST"])
def join_session(join_code):
    """An authenticated customer may join only their own ticket's session."""
    secret = _settings()
    user, customer = policy.customer()
    key = f"ss97:remote:join-attempts:{user}"
    attempts = int(frappe.cache().get_value(key) or 0)
    if attempts >= 5:
        frappe.throw("Trop d'essais. Veuillez réessayer plus tard.", frappe.PermissionError)
    try:
        digest = code_digest(normalize_code(join_code), secret)
    except ValueError:
        frappe.throw("Code invalide.", frappe.PermissionError)
    rows = frappe.get_all(SESSION, filters={"code_digest": digest},
                         fields=["name"], limit_page_length=1)
    if not rows:
        frappe.cache().set_value(key, attempts + 1, expires_in_sec=900)
        frappe.throw("Code invalide ou expiré.", frappe.PermissionError)
    session = _session(rows[0].name, lock=True)
    if session.customer != customer or session.client_user != user:
        frappe.cache().set_value(key, attempts + 1, expires_in_sec=900)
        frappe.throw("Code invalide ou expiré.", frappe.PermissionError)
    _authorized(session, "client")
    if _expired(session) or session.state != "CREATED":
        frappe.throw("Code invalide ou expiré.", frappe.PermissionError)
    return _transition(session, "CLIENT_READY", user)


@frappe.whitelist(methods=["POST"])
def decide_session(session_id, approve=0):
    """Portal acknowledgement, NOT the local MeshCentral desktop consent."""
    _settings()
    policy.customer()
    session = _session(session_id, lock=True)
    user = _authorized(session, "client")
    if _expired(session) or session.state != "CLIENT_READY":
        frappe.throw("Session non disponible.", frappe.PermissionError)
    if str(approve) not in ("0", "1"):
        frappe.throw("Décision invalide.", frappe.PermissionError)
    return _transition(session, "CLIENT_APPROVED" if str(approve) == "1" else "DECLINED", user)


@frappe.whitelist(methods=["GET"])
def get_session(session_id, audience="client"):
    _settings()
    if audience not in ("client", "technician"):
        frappe.throw("Espace invalide.", frappe.PermissionError)
    session = _session(session_id)
    _authorized(session, audience)
    return _view(session)


@frappe.whitelist(methods=["GET"])
def ticket_remote_history(ticket_name, audience="client"):
    _settings()
    if audience not in ("client", "technician"):
        frappe.throw("Espace invalide.", frappe.PermissionError)
    ticket = _issue(ticket_name)
    user = policy.authorize(ticket, audience)
    rows = frappe.get_all(SESSION, filters={"ticket_name": ticket.name,
        "client_user": ticket.raised_by, "customer": ticket.customer},
        fields=["name"], order_by="creation desc", limit_page_length=50)
    sessions = []
    for row in rows:
        session = _session(row.name)
        if audience == "client" or session.technician == user:
            sessions.append(_view(session))
    return {"sessions": sessions}


@frappe.whitelist(methods=["POST"])
def end_session(session_id, audience="client"):
    """Revoke a prepared session. Future real-engine sessions need hard disconnect."""
    _settings()
    if audience not in ("client", "technician"):
        frappe.throw("Espace invalide.", frappe.PermissionError)
    session = _session(session_id, lock=True)
    user = _authorized(session, audience)
    if session.state in TERMINAL:
        return _view(session)
    if session.state == "ACTIVE":
        # In V1 no engine can become ACTIVE. Never imply a live desktop was
        # disconnected until the future engine adapter confirms revocation.
        frappe.throw("Arrêt distant non confirmé : utilisez l'arrêt local MeshCentral.",
                     frappe.PermissionError)
    return _transition(session, "ENDED", user)


def expire_pending_sessions():
    """Scheduled housekeeping, never an invitation to silently remote-control."""
    config = frappe.conf.get("ss97_remote_assist") or {}
    if not isinstance(config, dict) or config.get("enabled") is not True:
        return
    rows = frappe.get_all(SESSION, filters={"state": ["in", list(PENDING)],
        "expires_at": ["<=", now_datetime()]}, fields=["name"], limit_page_length=200)
    for row in rows:
        session = _session(row.name, lock=True)
        if _expired(session):
            _transition(session, "EXPIRED", "system")
