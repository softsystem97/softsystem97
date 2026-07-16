# -*- coding: utf-8 -*-
"""API notifications portail client."""
from __future__ import annotations

import frappe
from frappe import _

from softsystem97.portal.customer import resolve_customer_for_user


def _uses_ss97_notifications() -> bool:
	return bool(frappe.db.exists("DocType", "SS97 Client Notification"))


def _notification_fields() -> list[str]:
	if _uses_ss97_notifications():
		return [
			"name",
			"title",
			"message",
			"notification_type",
			"is_read",
			"creation",
			"modified",
			"reference_doctype",
			"reference_name",
			"customer",
		]
	return [
		"name",
		"subject as title",
		"email_content as message",
		"type as notification_type",
		"read as is_read",
		"creation",
		"modified",
		"document_type as reference_doctype",
		"document_name as reference_name",
	]


def _base_filters(user: str) -> dict:
	return {"for_user": user}


@frappe.whitelist()
def get_my_notifications(limit: int = 50, offset: int = 0, unread_only: int = 0) -> dict:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Connexion requise."), frappe.PermissionError)

	customer = resolve_customer_for_user(user)
	doctype = "SS97 Client Notification" if _uses_ss97_notifications() else "Notification Log"
	filters = _base_filters(user)
	if unread_only:
		filters["is_read" if doctype == "SS97 Client Notification" else "read"] = 0
	if customer and doctype == "SS97 Client Notification":
		filters["customer"] = customer

	rows = frappe.get_all(
		doctype,
		filters=filters,
		fields=_notification_fields(),
		order_by="creation desc",
		limit_start=int(offset),
		limit_page_length=int(limit),
	)

	unread_field = "is_read" if doctype == "SS97 Client Notification" else "read"
	unread_filters = dict(filters)
	unread_filters[unread_field] = 0
	unread_count = frappe.db.count(doctype, unread_filters)

	return {
		"notifications": rows,
		"unread_count": unread_count,
		"total": len(rows),
	}


@frappe.whitelist()
def mark_read(name: str) -> dict:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Connexion requise."), frappe.PermissionError)

	doctype = "SS97 Client Notification" if _uses_ss97_notifications() else "Notification Log"
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("Notification introuvable."), frappe.DoesNotExistError)

	owner = frappe.db.get_value(doctype, name, "for_user")
	if owner != user:
		frappe.throw(_("Accès refusé."), frappe.PermissionError)

	field = "is_read" if doctype == "SS97 Client Notification" else "read"
	frappe.db.set_value(doctype, name, field, 1, update_modified=True)
	frappe.db.commit()
	return {"ok": True, "name": name}


@frappe.whitelist()
def mark_all_read() -> dict:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Connexion requise."), frappe.PermissionError)

	if _uses_ss97_notifications():
		names = frappe.get_all(
			"SS97 Client Notification",
			filters={"for_user": user, "is_read": 0},
			pluck="name",
		)
		for n in names:
			frappe.db.set_value("SS97 Client Notification", n, "is_read", 1, update_modified=False)
	else:
		names = frappe.get_all(
			"Notification Log",
			filters={"for_user": user, "read": 0},
			pluck="name",
		)
		for n in names:
			frappe.db.set_value("Notification Log", n, "read", 1, update_modified=False)

	frappe.db.commit()
	return {"ok": True, "updated": len(names)}


@frappe.whitelist()
def delete_notification(name: str) -> dict:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Connexion requise."), frappe.PermissionError)

	if not _uses_ss97_notifications():
		frappe.throw(_("Suppression non supportée pour Notification Log."), frappe.PermissionError)

	owner = frappe.db.get_value("SS97 Client Notification", name, "for_user")
	if owner != user:
		frappe.throw(_("Accès refusé."), frappe.PermissionError)

	frappe.delete_doc("SS97 Client Notification", name, ignore_permissions=True)
	frappe.db.commit()
	return {"ok": True, "name": name}
