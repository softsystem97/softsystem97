"""Opt-in SS97 V2–V20 case records backed by Frappe/ERPNext v16.

The module does not command MeshCentral, scan devices, initiate payments,
approve external partners, or call AI. It reuses the reviewed ticket bridge
for both tenant isolation and authorization. No public guest write endpoint.
"""

import json
from datetime import datetime
from uuid import uuid4

import frappe
from frappe.utils import now_datetime

from softsystem97.integrations.ticket_bridge import policy
from .registry import (
    EXTENDED_VERSIONS, MODULES, can_change_state, catalog, overlaps,
    schedule_window, validate_payload,
)


RECORD = "SS97 Platform Record"
EVENT = "SS97 Platform Event"


def _enabled():
    config = frappe.conf.get("ss97_v1_v10") or {}
    if not isinstance(config, dict) or config.get("enabled") is not True:
        frappe.throw("Modules SS97 V2–V10 non activés.", frappe.PermissionError)
    policy.settings()
    if not frappe.db.table_exists(RECORD) or not frappe.db.table_exists(EVENT):
        frappe.throw("Migration SS97 V2–V10 manquante.", frappe.PermissionError)


def _available_versions():
    """V11–V20 need a separate, explicitly enabled pilot flag."""
    config = frappe.conf.get("ss97_v11_v20") or {}
    extended_enabled = isinstance(config, dict) and config.get("enabled") is True
    return tuple(version for version in MODULES
                 if extended_enabled or version not in EXTENDED_VERSIONS)


def _require_version(version):
    if version not in _available_versions():
        frappe.throw("Version non activée sur ce site.", frappe.PermissionError)


def _ticket(ticket_name, audience):
    if not isinstance(ticket_name, str) or not (1 <= len(ticket_name) <= 140):
        frappe.throw("Ticket invalide.", frappe.PermissionError)
    if audience not in ("technician", "client"):
        frappe.throw("Espace invalide.", frappe.PermissionError)
    if not frappe.db.exists("Issue", ticket_name):
        frappe.throw("Ticket inaccessible.", frappe.PermissionError)
    ticket = frappe.get_doc("Issue", ticket_name)
    actor = policy.authorize(ticket, audience)
    if not ticket.customer or not ticket.raised_by:
        frappe.throw("Ticket sans client vérifié.", frappe.PermissionError)
    return ticket, actor


def _record(record_id, lock=False):
    if not isinstance(record_id, str) or len(record_id) != 36:
        frappe.throw("Dossier invalide.", frappe.PermissionError)
    if not frappe.db.exists(RECORD, record_id):
        frappe.throw("Dossier inaccessible.", frappe.PermissionError)
    return frappe.get_doc(RECORD, record_id, for_update=lock)


def _view(record):
    # All stored fields are validated on insertion. Never include secrets.
    return {
        "record_id": record.name, "ticket_name": record.ticket_name,
        "version": record.version, "title": record.title,
        "state": record.state, "technician": record.technician or "",
        "payload": json.loads(record.payload_json),
        "created_at": str(record.creation),
        "starts_at": record.starts_at or "",
        "ends_at": record.ends_at or "",
    }


def _log(record, action, user):
    frappe.get_doc({
        "doctype": EVENT, "event_id": str(uuid4()),
        "record_id": record.name, "action": action,
        "actor": user, "occurred_at": now_datetime(),
    }).insert(ignore_permissions=True)


def _validate_asset_link(version, payload, ticket):
    if version != "V7":
        return
    asset = frappe.db.get_value(
        RECORD, payload["asset_record"],
        ["version", "ticket_name", "customer", "state"], as_dict=True,
    )
    if (not asset or asset.version != "V6" or asset.ticket_name != ticket.name
            or asset.customer != ticket.customer or asset.state == "CANCELLED"):
        frappe.throw("Équipement non autorisé pour ce ticket.", frappe.PermissionError)


def _reserve_schedule(technician, start, end):
    """Lock the shared technician row to serialize concurrent assignments."""
    rows = frappe.db.sql(
        "SELECT name FROM `tabUser` WHERE name = %s FOR UPDATE", (technician,),
    )
    if not rows:
        frappe.throw("Technicien introuvable.", frappe.PermissionError)
    existing = frappe.get_all(
        RECORD,
        filters={"version": "V2", "technician": technician,
                 "state": ["in", ["SUBMITTED", "IN_REVIEW"]]},
        fields=["starts_at", "ends_at"], limit_page_length=1001,
    )
    if len(existing) > 1000:
        frappe.throw("Planning trop volumineux : vérification requise.", frappe.PermissionError)
    for row in existing:
        if not row.starts_at or not row.ends_at:
            frappe.throw("Créneau existant incomplet.", frappe.PermissionError)
        try:
            other_start = datetime.fromisoformat(row.starts_at.replace("Z", "+00:00"))
            other_end = datetime.fromisoformat(row.ends_at.replace("Z", "+00:00"))
        except ValueError:
            frappe.throw("Créneau existant invalide.", frappe.PermissionError)
        if overlaps(start, end, other_start, other_end):
            frappe.throw("Le technicien possède déjà une mission à cet horaire.", frappe.PermissionError)


@frappe.whitelist(methods=["GET"])
def get_catalog():
    _enabled()
    policy.active_user()
    return {"modules": catalog(_available_versions()), "v1": "SS97 Remote Assist : coordination séparée",
            "notice": "Dossiers administratifs uniquement : aucune connexion MeshCentral, commande, IA, supervision ou paiement autonome."}


@frappe.whitelist(methods=["POST"])
def create_record(version, ticket_name, payload_json, audience="technician"):
    """Create a server-bound customer/ticket record from a strict schema."""
    _enabled()
    if not isinstance(version, str) or version not in MODULES:
        frappe.throw("Version inconnue.", frappe.PermissionError)
    _require_version(version)
    if audience == "client" and version != "V5":
        frappe.throw("Seules les demandes SOS sont ouvertes au client.", frappe.PermissionError)
    ticket, user = _ticket(ticket_name, audience)
    if ticket.status == "Closed":
        frappe.throw("Ticket fermé.", frappe.PermissionError)
    if not isinstance(payload_json, str) or len(payload_json) > 12000:
        frappe.throw("Données invalides.", frappe.PermissionError)
    try:
        payload = validate_payload(version, json.loads(payload_json))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        frappe.throw(str(exc), frappe.PermissionError)
    _validate_asset_link(version, payload, ticket)
    starts_at = ends_at = ""
    if version == "V2":
        start, end = schedule_window(payload)
        _reserve_schedule(user, start, end)
        starts_at = start.isoformat().replace("+00:00", "Z")
        ends_at = end.isoformat().replace("+00:00", "Z")
    title_field = next(iter(MODULES[version]["required"]))
    title = str(payload[title_field])[:120]
    record = frappe.get_doc({
        "doctype": RECORD, "record_id": str(uuid4()),
        "ticket_name": ticket.name, "customer": ticket.customer,
        "technician": user if audience == "technician" else None,
        "created_by_user": user, "version": version,
        "title": title, "payload_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        "state": "SUBMITTED", "starts_at": starts_at, "ends_at": ends_at,
    }).insert(ignore_permissions=True)
    _log(record, "SUBMITTED", user)
    return _view(record)


@frappe.whitelist(methods=["GET"])
def list_records(ticket_name, audience="client"):
    _enabled()
    ticket, _ = _ticket(ticket_name, audience)
    rows = frappe.get_all(
        RECORD, filters={"ticket_name": ticket.name, "customer": ticket.customer,
                         "version": ["in", list(_available_versions())]},
        fields=["name"], order_by="creation desc", limit_page_length=100,
    )
    return {"records": [_view(_record(row.name)) for row in rows], "limit": 100}


@frappe.whitelist(methods=["GET"])
def get_case_overview(ticket_name, audience="client"):
    """V4 unified *read-only* ticket + V1 and V2–V10 progress overview."""
    _enabled()
    ticket, user = _ticket(ticket_name, audience)
    records = list_records(ticket_name, audience)["records"]
    remote_sessions = []
    if frappe.db.table_exists("SS97 Remote Session"):
        filters = {
            "ticket_name": ticket.name, "customer": ticket.customer,
            "client_user": ticket.raised_by,
        }
        if audience == "technician":
            filters["technician"] = user
        rows = frappe.get_all(
            "SS97 Remote Session", filters=filters,
            fields=["name", "state", "technician", "expires_at"],
            order_by="creation desc", limit_page_length=20,
        )
        remote_sessions = [{"session_id": item.name, "state": item.state,
                            "technician": item.technician, "expires_at": str(item.expires_at)}
                           for item in rows]
    return {"ticket_name": ticket.name, "ticket_status": ticket.status,
            "remote_sessions": remote_sessions,
            "modules": [{"version": version,
                         "total": sum(1 for record in records if record["version"] == version),
                         "open": sum(1 for record in records if record["version"] == version
                                     and record["state"] in ("SUBMITTED", "IN_REVIEW"))}
                        for version in _available_versions()],
            "record_limit": 100, "session_limit": 20}


@frappe.whitelist(methods=["GET"])
def get_record(record_id, audience="client"):
    _enabled()
    record = _record(record_id)
    _require_version(record.version)
    ticket, _ = _ticket(record.ticket_name, audience)
    if record.customer != ticket.customer:
        frappe.throw("Dossier inaccessible.", frappe.PermissionError)
    return _view(record)


@frappe.whitelist(methods=["POST"])
def set_record_state(record_id, state, audience="technician"):
    _enabled()
    record = _record(record_id, lock=True)
    _require_version(record.version)
    ticket, user = _ticket(record.ticket_name, audience)
    if record.customer != ticket.customer:
        frappe.throw("Dossier inaccessible.", frappe.PermissionError)
    if not can_change_state(record.state, state, audience, record.version):
        frappe.throw("Changement d'état interdit.", frappe.PermissionError)
    if state == "COMPLETED" and ticket.status == "Closed":
        frappe.throw("Ticket déjà fermé.", frappe.PermissionError)
    record.state = state
    record.save(ignore_permissions=True)
    _log(record, state, user)
    return _view(record)
