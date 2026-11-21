"""CyberExpert 360 CyberOS v1: customer-scoped inventory, actions, incidents.

Explicitly no automated scanning, cyberattack response, remote access, payouts,
credits, AI provider calls, or collection of passwords. All writes are isolated
to the uniquely mapped and active ERPNext Customer, with audit history.
"""
from uuid import uuid4

import frappe

from .logic import (CLIENT_ACTION_STATES, action_data, asset_data,
                    choice, identifier, incident_data, text)

ASSET = "SS97 Cyber Asset"
ACTION = "SS97 Cyber Action"
INCIDENT = "SS97 Cyber Incident"
DOCTYPES = (ASSET, ACTION, INCIDENT)


def _enabled():
    config = frappe.conf.get("ss97_cyberos")
    bridge = frappe.conf.get("ss97_ticket_bridge")
    if (not isinstance(config, dict) or config.get("enabled") is not True
            or not isinstance(bridge, dict) or bridge.get("enabled") is not True
            or bridge.get("compatibility_confirmed") is not True):
        frappe.throw("CyberOS en préparation : accès non activé.", frappe.PermissionError)
    if not all(frappe.db.exists("DocType", doctype) for doctype in DOCTYPES):
        frappe.throw("Migration CyberOS requise.", frappe.PermissionError)


def _user():
    user = frappe.session.user
    if not user or user == "Guest" or not frappe.db.get_value("User", user, "enabled"):
        frappe.throw("Compte client actif requis.", frappe.PermissionError)
    return user


def _company():
    _enabled()
    user = _user()
    from softsystem97.integrations.ticket_bridge.policy import client_customer_for_user
    customer = client_customer_for_user(user)
    if not customer:
        frappe.throw("Compte client non associé à une entreprise unique.", frappe.PermissionError)
    return user, customer


def _manager():
    _enabled()
    user = _user()
    if "System Manager" not in frappe.get_roles(user):
        frappe.throw("Validation réservée à la direction.", frappe.PermissionError)
    return user


def _owned(doctype, name, customer, lock=False):
    name = identifier(name)
    if not frappe.db.exists(doctype, name):
        frappe.throw("Dossier inexistant.", frappe.PermissionError)
    doc = frappe.get_doc(doctype, name, for_update=lock)
    if doc.customer != customer:
        frappe.throw("Dossier inaccessible.", frappe.PermissionError)
    return doc


def _rows(doctype, customer, fields, limit=100):
    return frappe.get_all(doctype, filters={"customer": customer},
                          fields=fields, order_by="creation desc",
                          limit_page_length=limit)


@frappe.whitelist(methods=["GET"])
def get_my_command_center():
    """Never return another tenant's data or hidden credentials."""
    user, company = _company()
    fields = {"assets": ["name", "label", "kind", "criticality", "business_service", "creation"],
              "actions": ["name", "summary", "category", "priority", "state", "asset", "creation"],
              "incidents": ["name", "summary", "severity", "state", "creation"]}
    assets = _rows(ASSET, company, fields["assets"])
    actions = _rows(ACTION, company, fields["actions"])
    incidents = _rows(INCIDENT, company, fields["incidents"])
    return {
        "customer": company, "user": user,
        "assets": assets, "actions": actions, "incidents": incidents,
        "counts": {
            "assets": frappe.db.count(ASSET, {"customer": company}),
            "actions_open": frappe.db.count(ACTION, {"customer": company,
                "state": ["in", ["OPEN", "IN_PROGRESS", "DONE_DECLARED"]]}),
            "incidents_open": frappe.db.count(INCIDENT, {"customer": company,
                "state": ["in", ["REPORTED", "UNDER_REVIEW"]]}),
        },
        "capabilities": {
            "inventory": "available", "action_plan": "available",
            "incident_register": "available",
            "auto_scanning": "not_enabled", "ai_copilot": "not_connected",
            "security_monitoring": "not_connected",
        },
        "disclaimer": "Données déclaratives. Aucun audit, surveillance ou réponse d'urgence 24 h/24 n'est garanti.",
    }


@frappe.whitelist(methods=["POST"])
def register_asset(label, kind, criticality, business_service):
    user, customer = _company()
    try:
        data = asset_data(label, kind, criticality, business_service)
    except ValueError as exc:
        frappe.throw(str(exc), frappe.ValidationError)
    doc = frappe.get_doc({"doctype": ASSET, "asset_id": str(uuid4()),
                          "customer": customer, "created_by_user": user, **data})
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "label": doc.label}


@frappe.whitelist(methods=["POST"])
def create_action(summary, category, priority, asset=None):
    user, customer = _company()
    try:
        data = action_data(summary, category, priority, asset)
    except ValueError as exc:
        frappe.throw(str(exc), frappe.ValidationError)
    if data["asset"]:
        _owned(ASSET, data["asset"], customer)
    doc = frappe.get_doc({"doctype": ACTION, "action_id": str(uuid4()),
                          "customer": customer, "created_by_user": user,
                          "state": "OPEN", **data})
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "state": doc.state}


@frappe.whitelist(methods=["POST"])
def update_my_action(name, state):
    _, customer = _company()
    try:
        choice(state, CLIENT_ACTION_STATES, "État de l'action")
    except ValueError as exc:
        frappe.throw(str(exc), frappe.ValidationError)
    doc = _owned(ACTION, name, customer, lock=True)
    if doc.state == "VERIFIED":
        frappe.throw("Une validation humaine ne peut être annulée par le client.", frappe.PermissionError)
    doc.state = state
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "state": doc.state}


@frappe.whitelist(methods=["POST"])
def report_incident(summary, severity, description):
    user, customer = _company()
    try:
        data = incident_data(summary, severity, description)
    except ValueError as exc:
        frappe.throw(str(exc), frappe.ValidationError)
    doc = frappe.get_doc({"doctype": INCIDENT, "incident_id": str(uuid4()),
                          "customer": customer, "reported_by": user,
                          "state": "REPORTED", **data})
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "state": doc.state,
            "notice": "Déclaration enregistrée. Aucun service d'urgence ni d'astreinte n'est déclenché."}


@frappe.whitelist(methods=["POST"])
def verify_action(name, evidence_reference):
    """Human manager-only verification; client cannot self-certify."""
    user = _manager()
    try:
        reference = text(evidence_reference, 160, "Référence de preuve")
        if len(reference) < 10:
            raise ValueError("Référence de preuve trop courte.")
        name = identifier(name)
    except ValueError as exc:
        frappe.throw(str(exc), frappe.ValidationError)
    if not frappe.db.exists(ACTION, name):
        frappe.throw("Action inconnue.", frappe.PermissionError)
    doc = frappe.get_doc(ACTION, name, for_update=True)
    if doc.state != "DONE_DECLARED":
        frappe.throw("Une action doit d'abord être déclarée terminée.", frappe.PermissionError)
    doc.state = "VERIFIED"
    doc.verified_by = user
    doc.verified_at = frappe.utils.now_datetime()
    doc.evidence_reference = reference
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "state": doc.state, "verified_by": user}


@frappe.whitelist(methods=["POST"])
def triage_incident(name, state):
    """Management triage does not trigger external interventions or alerts."""
    _manager()
    try:
        name = identifier(name)
        choice(state, ("UNDER_REVIEW", "CLOSED"), "Statut incident")
    except ValueError as exc:
        frappe.throw(str(exc), frappe.ValidationError)
    if not frappe.db.exists(INCIDENT, name):
        frappe.throw("Incident inconnu.", frappe.PermissionError)
    doc = frappe.get_doc(INCIDENT, name, for_update=True)
    if doc.state == "CLOSED" and state != "CLOSED":
        frappe.throw("Incident clos : réouverture par une nouvelle déclaration.", frappe.PermissionError)
    doc.state = state
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "state": doc.state}
