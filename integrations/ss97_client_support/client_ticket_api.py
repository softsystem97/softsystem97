# -*- coding: utf-8 -*-
"""API portail client cloisonnée pour les tickets ERPNext.

Les Website Users n'obtiennent aucun rôle Issue global. Chaque opération
vérifie l'adresse de la session contre ``raised_by``/``ss97_contact_email``.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from migrate_odoo_erpnext.erpnext_client import ERPNextClient

SCRIPT_NAME = "SS97 Client Ticket API"
API_METHOD = "ss97_client_ticket_api"


SERVER_SCRIPT = r'''
user = frappe.session.user
if not user or user == "Guest":
    frappe.throw("Connexion client requise", frappe.AuthenticationError)
if not frappe.db.get_value("User", user, "enabled"):
    frappe.throw("Compte désactivé", frappe.PermissionError)

action = (frappe.form_dict.get("action") or "list").strip().lower()
allowed_priorities = ["Low", "Medium", "High", "Urgent"]
ticket_fields = [
    "name", "subject", "description", "status", "priority", "creation", "modified",
    "raised_by", "ss97_contact_email", "ss97_public_ref", "ss97_ticket_status",
    "ss97_payment_status", "ss97_payment_ref", "ss97_invoice_amount", "ss97_contract_ref",
    "ss97_stripe_checkout_url",
    "ss97_category", "ss97_source", "ss97_device_summary", "ss97_technician",
    "ss97_appointment_on", "ss97_intervention_started_on", "ss97_resolved_on",
    "ss97_intervention_report", "ss97_intervention_address",
]

def shared_comment(row):
    # Unknown/native notes are private by default. UI filtering is not authorization.
    text = frappe.utils.strip_html(row.get("content") or "").strip().lower()
    private_markers = ["[interne]", "tech_private", "note privée", "note privee",
        "technicien→administrateur", "technicien → administrateur",
        "admin→technicien", "admin → technicien"]
    if row.get("comment_type") != "Comment":
        return False
    for marker in private_markers:
        if marker in text:
            return False
    public_prefixes = ["[client]", "[client→technicien]", "[client → technicien]",
        "[technicien→client]", "[technicien → client]", "[admin→client]",
        "[administrateur→client]", "[ss97 client chatbot]"]
    for prefix in public_prefixes:
        if text.startswith(prefix):
            return True
    return False

def owned(name):
    row = frappe.db.get_value(
        "Issue", name, ["name", "raised_by", "ss97_contact_email"], as_dict=1
    )
    if not row:
        frappe.throw("Ticket inaccessible", frappe.PermissionError)
    owner_email = (row.get("raised_by") or "").strip().lower()
    contact_email = (row.get("ss97_contact_email") or "").strip().lower()
    if user.strip().lower() not in [owner_email, contact_email]:
        frappe.throw("Ticket inaccessible", frappe.PermissionError)
    return row

if action == "list":
    by_name = {}
    for row in frappe.get_all(
        "Issue", filters={"raised_by": user}, fields=ticket_fields,
        order_by="modified desc", limit_page_length=100
    ):
        by_name[row.get("name")] = row
    for row in frappe.get_all(
        "Issue", filters={"ss97_contact_email": user}, fields=ticket_fields,
        order_by="modified desc", limit_page_length=100
    ):
        by_name[row.get("name")] = row
    rows = list(by_name.values())
    rows.sort(key=lambda item: str(item.get("modified") or ""), reverse=True)
    frappe.response["message"] = rows[:100]

elif action == "get":
    name = (frappe.form_dict.get("name") or "").strip()
    owned(name)
    doc = frappe.get_doc("Issue", name).as_dict()
    safe_doc = {}
    for field in ticket_fields:
        safe_doc[field] = doc.get(field)
    comments = frappe.get_all(
        "Comment",
        filters={"reference_doctype": "Issue", "reference_name": name},
        fields=["name", "comment_type", "content", "comment_email", "creation", "owner"],
        order_by="creation asc", limit_page_length=200,
    )
    comments = [row for row in comments if shared_comment(row)]
    # Native File permissions must decide disclosure; attachment alone is not consent.
    files = []
    try:
        files = frappe.get_list("File",
            filters={"attached_to_doctype": "Issue", "attached_to_name": name},
            fields=["name", "file_name", "file_url", "is_private", "file_size", "creation"],
            order_by="creation asc", limit_page_length=100)
    except frappe.PermissionError:
        pass  # No fallback to get_all: unavailable attachments remain private.
    frappe.response["message"] = {"doc": safe_doc, "comments": comments, "files": files}

elif action == "create":
    frappe.throw(
        "Utilisez le parcours sécurisé : paiement à l'unité ou abonnement actif.",
        frappe.PermissionError,
    )

elif action == "comment":
    # Server Script API dispatch bypasses native whitelist HTTP-method checks.
    # The app gate explicitly enforces POST; native Frappe still enforces CSRF.
    frappe.call("softsystem97.integrations.historical_ticket_guard.require_write_session")
    name = (frappe.form_dict.get("name") or "").strip()
    owned(name)
    content = (frappe.form_dict.get("content") or "").strip()
    if len(content) < 1 or len(content) > 5000:
        frappe.throw("Le message doit contenir entre 1 et 5000 caractères")
    comment = frappe.get_doc({
        "doctype": "Comment", "comment_type": "Comment",
        "reference_doctype": "Issue", "reference_name": name,
        "content": "[Client] " + frappe.utils.escape_html(content),
    })
    comment.insert(ignore_permissions=True)
    frappe.response["message"] = {"ok": True, "name": comment.name}

else:
    frappe.throw("Action portail ticket non autorisée")
'''


def ensure_client_ticket_api(client: ERPNextClient) -> str:
    """Crée ou met à jour l'API sans jamais activer l'accès invité."""
    rows = client.list_docs(
        "Server Script",
        filters=[["api_method", "=", API_METHOD]],
        fields=["name"],
        limit=1,
    ) or []
    payload = {
        "script_type": "API",
        "api_method": API_METHOD,
        "allow_guest": 0,
        "disabled": 0,
        "script": SERVER_SCRIPT,
    }
    if rows:
        name = rows[0]["name"]
        client.update("Server Script", name, payload)
        return f"updated:{name}"
    client.insert({"doctype": "Server Script", "name": SCRIPT_NAME, **payload})
    return f"created:{SCRIPT_NAME}"


def deploy(client: ERPNextClient | None = None) -> str:
    from migrate_odoo_erpnext.erpnext_client import ERPNextClient

    return ensure_client_ticket_api(client or ERPNextClient.from_env())


if __name__ == "__main__":
    print(deploy())
