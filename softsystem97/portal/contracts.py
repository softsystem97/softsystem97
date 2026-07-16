# -*- coding: utf-8 -*-
"""API contrats portail client — workflow signature."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, today

from softsystem97.portal.customer import require_customer, resolve_customer_for_user

# Statuts métier SoftSystem97
SS97_CONTRACT_STATUSES = (
	"Draft",
	"À vérifier",
	"Envoyé",
	"Consulté",
	"À signer",
	"Signé",
	"Refusé",
	"Expiré",
	"Annulé",
	"Renouvelé",
	"Archivé",
)

# Mapping ERPNext Contract.status → ss97_contract_status
ERP_TO_SS97_STATUS = {
	"Unsigned": "À signer",
	"Active": "Signé",
	"Inactive": "Archivé",
}

SS97_TO_ERP_STATUS = {
	"Draft": "Unsigned",
	"À vérifier": "Unsigned",
	"Envoyé": "Unsigned",
	"Consulté": "Unsigned",
	"À signer": "Unsigned",
	"Signé": "Active",
	"Refusé": "Inactive",
	"Expiré": "Inactive",
	"Annulé": "Inactive",
	"Renouvelé": "Active",
	"Archivé": "Inactive",
}

SIGNABLE_STATUSES = frozenset({"Envoyé", "Consulté", "À signer"})
REFUSABLE_STATUSES = frozenset({"Envoyé", "Consulté", "À signer"})


def _has_ss97_contract_status() -> bool:
	return frappe.get_meta("Contract").has_field("ss97_contract_status")


def get_contract_status(doc) -> str:
	if _has_ss97_contract_status() and doc.get("ss97_contract_status"):
		return doc.ss97_contract_status
	return ERP_TO_SS97_STATUS.get(doc.status, doc.status or "Draft")


def set_contract_status(doc, status: str) -> None:
	if status not in SS97_CONTRACT_STATUSES:
		frappe.throw(_("Statut contrat invalide: {0}").format(status))

	if _has_ss97_contract_status():
		doc.ss97_contract_status = status
	erp_status = SS97_TO_ERP_STATUS.get(status)
	if erp_status:
		doc.status = erp_status
	if status == "Signé" and frappe.get_meta("Contract").has_field("ss97_signed_on"):
		doc.ss97_signed_on = now_datetime()
	if status == "Signé":
		doc.is_active = 1
	if status in ("Refusé", "Annulé", "Expiré", "Archivé"):
		doc.is_active = 0


def _contract_fields() -> list[str]:
	fields = [
		"name",
		"party_name",
		"start_date",
		"end_date",
		"status",
		"is_active",
		"contract_terms",
		"modified",
		"creation",
	]
	meta = frappe.get_meta("Contract")
	for f in (
		"ss97_contract_status",
		"ss97_signed_on",
		"ss97_sent_on",
		"ss97_viewed_on",
		"ss97_refusal_reason",
		"ss97_modification_request",
	):
		if meta.has_field(f):
			fields.append(f)
	return fields


def _assert_contract_access(contract_name: str, customer: str) -> frappe.model.document.Document:
	if not frappe.db.exists("Contract", contract_name):
		frappe.throw(_("Contrat introuvable."), frappe.DoesNotExistError)

	doc = frappe.get_doc("Contract", contract_name)
	if doc.party_type != "Customer" or doc.party_name != customer:
		frappe.throw(_("Accès refusé."), frappe.PermissionError)
	return doc


def serialize_contract(doc) -> dict:
	data = doc.as_dict()
	data["ss97_status"] = get_contract_status(doc)
	return data


def serialize_contract_list(customer: str, limit: int = 50) -> list[dict]:
	rows = frappe.get_all(
		"Contract",
		filters={"party_name": customer, "party_type": "Customer"},
		fields=_contract_fields(),
		order_by="modified desc",
		limit_page_length=limit,
	)
	for row in rows:
		if _has_ss97_contract_status() and row.get("ss97_contract_status"):
			row["ss97_status"] = row["ss97_contract_status"]
		else:
			row["ss97_status"] = ERP_TO_SS97_STATUS.get(row.get("status"), row.get("status"))
	return rows


def _check_expiry(doc) -> None:
	if doc.end_date and getdate(doc.end_date) < getdate(today()):
		current = get_contract_status(doc)
		if current not in ("Signé", "Renouvelé", "Archivé", "Annulé"):
			set_contract_status(doc, "Expiré")


@frappe.whitelist()
def list_my_contracts(limit: int = 50, customer: str | None = None) -> dict:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Connexion requise."), frappe.PermissionError)

	resolved = resolve_customer_for_user(user, customer)
	if not resolved:
		return {"customer": None, "contracts": []}

	return {"customer": resolved, "contracts": serialize_contract_list(resolved, limit=int(limit))}


@frappe.whitelist()
def get_contract(name: str, customer: str | None = None) -> dict:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Connexion requise."), frappe.PermissionError)

	resolved = require_customer(user, customer)
	doc = _assert_contract_access(name, resolved)
	_check_expiry(doc)
	if doc.has_value_changed("status") or (
		_has_ss97_contract_status() and doc.has_value_changed("ss97_contract_status")
	):
		doc.save(ignore_permissions=True)
		frappe.db.commit()

	current = get_contract_status(doc)
	if current == "Envoyé":
		set_contract_status(doc, "Consulté")
		if frappe.get_meta("Contract").has_field("ss97_viewed_on"):
			doc.ss97_viewed_on = now_datetime()
		doc.save(ignore_permissions=True)
		frappe.db.commit()

	return {"contract": serialize_contract(doc)}


@frappe.whitelist()
def sign_contract(name: str, customer: str | None = None, signature_note: str | None = None) -> dict:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Connexion requise."), frappe.PermissionError)

	resolved = require_customer(user, customer)
	doc = _assert_contract_access(name, resolved)
	current = get_contract_status(doc)

	if current not in SIGNABLE_STATUSES:
		frappe.throw(_("Ce contrat ne peut pas être signé (statut: {0}).").format(current))

	set_contract_status(doc, "Signé")
	if frappe.get_meta("Contract").has_field("ss97_signature_note") and signature_note:
		doc.ss97_signature_note = signature_note

	doc.save(ignore_permissions=True)
	_add_contract_comment(doc.name, f"<p><b>Contrat signé</b> par {frappe.utils.escape_html(user)}</p>")
	frappe.db.commit()
	return {"ok": True, "contract": serialize_contract(doc)}


@frappe.whitelist()
def refuse_contract(name: str, reason: str | None = None, customer: str | None = None) -> dict:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Connexion requise."), frappe.PermissionError)

	if not (reason or "").strip():
		frappe.throw(_("Motif de refus requis."))

	resolved = require_customer(user, customer)
	doc = _assert_contract_access(name, resolved)
	current = get_contract_status(doc)

	if current not in REFUSABLE_STATUSES:
		frappe.throw(_("Ce contrat ne peut pas être refusé (statut: {0}).").format(current))

	set_contract_status(doc, "Refusé")
	if frappe.get_meta("Contract").has_field("ss97_refusal_reason"):
		doc.ss97_refusal_reason = reason.strip()

	doc.save(ignore_permissions=True)
	_add_contract_comment(
		doc.name,
		f"<p><b>Contrat refusé</b> — {frappe.utils.escape_html(reason.strip())}</p>",
	)
	frappe.db.commit()
	return {"ok": True, "contract": serialize_contract(doc)}


@frappe.whitelist()
def request_modification(name: str, message: str | None = None, customer: str | None = None) -> dict:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Connexion requise."), frappe.PermissionError)

	if not (message or "").strip():
		frappe.throw(_("Message de modification requis."))

	resolved = require_customer(user, customer)
	doc = _assert_contract_access(name, resolved)
	current = get_contract_status(doc)

	if current in ("Signé", "Archivé", "Annulé", "Refusé"):
		frappe.throw(_("Modification impossible pour le statut: {0}").format(current))

	if frappe.get_meta("Contract").has_field("ss97_modification_request"):
		doc.ss97_modification_request = message.strip()
	set_contract_status(doc, "À vérifier")
	doc.save(ignore_permissions=True)
	_add_contract_comment(
		doc.name,
		f"<p><b>Demande de modification</b> — {frappe.utils.escape_html(message.strip())}</p>",
	)
	frappe.db.commit()
	return {"ok": True, "contract": serialize_contract(doc)}


def _add_contract_comment(contract_name: str, content: str) -> None:
	try:
		frappe.get_doc({
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Contract",
			"reference_name": contract_name,
			"content": content,
		}).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="SS97 contract comment failed", message=frappe.get_traceback())
