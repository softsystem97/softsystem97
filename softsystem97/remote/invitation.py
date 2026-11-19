"""Opt-in customer invitation producer for a prepared SS97 Remote Assist slot.

Never email the one-time join code or an engine/device identifier.  The recipient
comes from the verified ticket owner, never the technician's browser request.
Queue creation shares the caller's ticket/session transaction (no commit/flush).
"""

from html import escape

import frappe


def request_client_invitation(ticket):
    """Request one queued message only when the operator enabled test email."""
    config = frappe.conf.get("ss97_remote_assist") or {}
    if not isinstance(config, dict) or config.get("email_enabled") is not True:
        return False

    account_name = config.get("email_account")
    if not isinstance(account_name, str) or not account_name.strip():
        frappe.throw("Compte e-mail d'assistance non configuré.", frappe.PermissionError)
    outgoing = frappe.db.get_value(
        "Email Account", account_name.strip(),
        ["email_id", "enable_outgoing"], as_dict=True,
    )
    if not outgoing or not outgoing.enable_outgoing or not outgoing.email_id:
        frappe.throw("Compte e-mail sortant indisponible.", frappe.PermissionError)

    customer = frappe.db.get_value(
        "User", ticket.raised_by, ["email", "enabled"], as_dict=True,
    )
    if not customer or not customer.enabled or not customer.email:
        frappe.throw("Adresse du client associé indisponible.", frappe.PermissionError)

    # The caller already verified the ticket/Customer/Portal User identity,
    # payment gate, authorization and 1-hour unique-session lock.
    link = frappe.utils.get_url("/ss97-remote-assist")
    if not isinstance(link, str) or not link.startswith("https://"):
        frappe.throw("Adresse HTTPS de l'assistance non configurée.", frappe.PermissionError)
    safe_link = escape(link, quote=True)
    safe_ticket = escape(str(ticket.name))
    body = (
        "<p>Une demande d'assistance Soft System 97 a été préparée pour votre "
        f"ticket {safe_ticket}.</p>"
        f'<p><a href="{safe_link}">Accéder à votre espace d’assistance</a> '
        "et saisir le code à usage unique communiqué séparément par votre "
        "technicien.</p>"
        "<p>Aucun accès à votre ordinateur n'est accordé par cet e-mail. "
        "Vous pourrez accepter ou refuser la demande sur le portail, puis "
        "autoriser séparément le partage dans MeshCentral sur votre ordinateur. "
        "La demande expire au plus tard une heure après sa préparation.</p>"
        "<p>Si vous n'avez rien demandé, ignorez ce message et contactez "
        "Soft System 97 par vos coordonnées habituelles.</p>"
    )
    frappe.sendmail(
        recipients=[customer.email],
        sender=outgoing.email_id,
        subject="Soft System 97 — demande d'assistance en attente",
        message=body,
        delayed=True,
        reference_doctype="Issue",
        reference_name=ticket.name,
    )
    return True  # Queue requested, not SMTP delivery confirmed.
