# -*- coding: utf-8 -*-
"""Helpers Stripe → ERPNext (webhook, sync paiement)."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import frappe
from frappe.utils import cint, flt, now_datetime

REPLAY_TOLERANCE_SECONDS = 300

SUCCESS_STATUSES = frozenset({"paid", "no_payment_required", "succeeded"})
FAILURE_STATUSES = frozenset({"failed", "canceled", "payment_failed"})

HANDLED_EVENT_TYPES = frozenset({
	"checkout.session.completed",
	"payment_intent.succeeded",
	"payment_intent.payment_failed",
	"invoice.paid",
	"invoice.payment_failed",
	"customer.subscription.created",
	"customer.subscription.updated",
	"customer.subscription.deleted",
	"charge.refunded",
})


def payments_live_enabled() -> bool:
	val = frappe.conf.get("PAYMENTS_LIVE_ENABLED")
	if val is None:
		try:
			if frappe.db.exists("DocType", "SS97 Stripe Config"):
				val = frappe.db.get_single_value("SS97 Stripe Config", "payments_live_enabled")
		except Exception:
			val = None
	return cint(val) == 1


def stripe_mode() -> str:
	mode = (frappe.conf.get("STRIPE_MODE") or "").strip().lower()
	if not mode:
		try:
			if frappe.db.exists("DocType", "SS97 Stripe Config"):
				if frappe.db.get_single_value("SS97 Stripe Config", "test_mode"):
					mode = "test"
				else:
					mode = "live"
		except Exception:
			mode = "test"
	return mode or "test"


def get_webhook_secrets() -> tuple[str | None, str | None]:
	"""Retourne (test_secret, live_secret) sans jamais les logger."""
	test = (frappe.conf.get("STRIPE_TEST_WEBHOOK_SECRET") or "").strip() or None
	live = (frappe.conf.get("STRIPE_WEBHOOK_SECRET") or "").strip() or None

	if frappe.db.exists("DocType", "SS97 Stripe Config"):
		try:
			conf = frappe.get_single("SS97 Stripe Config")
			if getattr(conf, "test_webhook_secret", None):
				test = conf.get_password("test_webhook_secret") or test
			if getattr(conf, "webhook_secret", None):
				live = conf.get_password("webhook_secret") or live
		except Exception:
			pass

	return test, live


def verify_stripe_signature(payload: bytes, sig_header: str, secret: str, tolerance: int = REPLAY_TOLERANCE_SECONDS) -> bool:
	if not payload or not sig_header or not secret:
		return False

	timestamp: int | None = None
	signatures: list[str] = []
	for part in sig_header.split(","):
		part = part.strip()
		if "=" not in part:
			continue
		key, value = part.split("=", 1)
		if key == "t":
			try:
				timestamp = int(value)
			except ValueError:
				return False
		elif key == "v1":
			signatures.append(value)

	if timestamp is None or not signatures:
		return False

	if time.time() - timestamp > tolerance:
		return False

	body = payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)
	signed_payload = f"{timestamp}.{body}"
	expected = hmac.new(secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
	return any(hmac.compare_digest(expected, sig) for sig in signatures)


def resolve_webhook_secret(livemode: bool) -> str | None:
	test_secret, live_secret = get_webhook_secrets()
	if livemode:
		return live_secret
	return test_secret


def enforce_mode_policy(event: dict[str, Any]) -> None:
	livemode = bool(event.get("livemode"))
	if not payments_live_enabled() and livemode:
		frappe.throw("Mode LIVE désactivé (PAYMENTS_LIVE_ENABLED=0). Événement rejeté.", frappe.PermissionError)


def event_already_processed(stripe_event_id: str) -> bool:
	if not stripe_event_id or not frappe.db.exists("DocType", "SS97 Stripe Event"):
		return False
	status = frappe.db.get_value("SS97 Stripe Event", {"stripe_event_id": stripe_event_id}, "status")
	return status == "Success"


def log_stripe_event(
	stripe_event_id: str,
	event_type: str,
	*,
	customer: str | None = None,
	invoice: str | None = None,
	amount: float | None = None,
	currency: str | None = None,
	status: str = "Pending",
	result: str | None = None,
	error: str | None = None,
	livemode: bool = False,
) -> str | None:
	if not frappe.db.exists("DocType", "SS97 Stripe Event"):
		return None

	existing = frappe.db.get_value("SS97 Stripe Event", {"stripe_event_id": stripe_event_id}, "name")
	payload = {
		"doctype": "SS97 Stripe Event",
		"stripe_event_id": stripe_event_id,
		"event_type": event_type,
		"event_date": now_datetime(),
		"customer": customer,
		"invoice": invoice,
		"amount": amount,
		"currency": currency,
		"status": status,
		"result": (result or "")[:500] if result else None,
		"error": (error or "")[:500] if error else None,
		"livemode": 1 if livemode else 0,
	}

	try:
		if existing:
			doc = frappe.get_doc("SS97 Stripe Event", existing)
			doc.update({k: v for k, v in payload.items() if k != "doctype" and v is not None})
			doc.save(ignore_permissions=True)
			return doc.name
		doc = frappe.get_doc(payload)
		doc.insert(ignore_permissions=True)
		return doc.name
	except Exception as exc:
		frappe.log_error(title="SS97 Stripe Event log failed", message=frappe.get_traceback())
		return None


def _meta_get(obj: dict[str, Any]) -> dict[str, Any]:
	return obj.get("metadata") or {}


def _amount_from_cents(cents: Any) -> float:
	return flt(cents) / 100.0 if cents is not None else 0.0


def find_sales_invoice_from_stripe_object(obj: dict[str, Any]) -> str | None:
	meta = _meta_get(obj)
	invoice_name = (meta.get("invoice") or meta.get("erpnext_invoice") or "").strip()
	if invoice_name and frappe.db.exists("Sales Invoice", invoice_name):
		return invoice_name

	session_id = (obj.get("id") if obj.get("object") == "checkout.session" else None) or meta.get("session_id")
	if session_id:
		found = frappe.db.get_value("Sales Invoice", {"ss97_stripe_session_id": session_id}, "name")
		if found:
			return found

	payment_intent = obj.get("payment_intent") or (
		obj.get("id") if obj.get("object") == "payment_intent" else None
	)
	if isinstance(payment_intent, dict):
		payment_intent = payment_intent.get("id")
	if payment_intent:
		found = frappe.db.get_value("Sales Invoice", {"ss97_stripe_payment_intent": payment_intent}, "name")
		if found:
			return found

	if obj.get("object") == "charge":
		pi = obj.get("payment_intent")
		if pi:
			found = frappe.db.get_value("Sales Invoice", {"ss97_stripe_payment_intent": pi}, "name")
			if found:
				return found

	# invoice object may reference subscription metadata
	if obj.get("object") == "invoice":
		for sub_key in ("subscription_details", "parent", "lines"):
			pass
		inv_meta = _meta_get(obj)
		inv_name = (inv_meta.get("invoice") or "").strip()
		if inv_name and frappe.db.exists("Sales Invoice", inv_name):
			return inv_name

	return None


def verify_amount_currency(invoice_name: str, amount: float, currency: str | None) -> tuple[bool, str]:
	if not invoice_name:
		return True, ""
	inv = frappe.db.get_value(
		"Sales Invoice",
		invoice_name,
		["grand_total", "outstanding_amount", "currency"],
		as_dict=True,
	)
	if not inv:
		return False, "Facture introuvable"

	if currency and inv.currency and currency.upper() != (inv.currency or "").upper():
		return False, f"Devise incompatible ({currency} vs {inv.currency})"

	expected = flt(inv.outstanding_amount or inv.grand_total)
	if amount and expected and abs(amount - expected) > 0.05:
		return False, f"Montant divergent ({amount} vs {expected})"
	return True, ""


def _safe_set_invoice_field(invoice_name: str, fieldname: str, value: Any) -> None:
	if not invoice_name or not value:
		return
	try:
		meta = frappe.get_meta("Sales Invoice")
		if meta.has_field(fieldname):
			frappe.db.set_value("Sales Invoice", invoice_name, fieldname, value, update_modified=False)
	except Exception:
		pass


def update_invoice_stripe_fields(
	invoice_name: str,
	*,
	session_id: str | None = None,
	payment_intent: str | None = None,
	payment_status: str | None = None,
	receipt_ref: str | None = None,
	mode: str | None = None,
	paid_on: str | None = None,
) -> None:
	if not invoice_name:
		return
	mode = mode or stripe_mode()
	if session_id:
		_safe_set_invoice_field(invoice_name, "ss97_stripe_session_id", session_id)
	if payment_intent:
		_safe_set_invoice_field(invoice_name, "ss97_stripe_payment_intent", payment_intent)
	if mode:
		_safe_set_invoice_field(invoice_name, "ss97_stripe_mode", mode)
	if receipt_ref:
		_safe_set_invoice_field(invoice_name, "ss97_receipt_ref", receipt_ref)
	if paid_on:
		_safe_set_invoice_field(invoice_name, "ss97_paid_on", paid_on)
	if payment_status:
		_safe_set_invoice_field(invoice_name, "ss97_payment_status", payment_status)


def generate_receipt_ref() -> str:
	return "SS97-RCPT-" + now_datetime().strftime("%Y%m%d%H%M%S")


def create_payment_entry_for_invoice(invoice_name: str, amount: float, reference_no: str) -> str | None:
	if not invoice_name or not frappe.db.exists("Sales Invoice", invoice_name):
		return None

	inv = frappe.get_doc("Sales Invoice", invoice_name)
	if flt(inv.outstanding_amount) <= 0:
		return None

	try:
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

		pe = get_payment_entry("Sales Invoice", invoice_name, party_amount=amount or None)
		pe.reference_no = reference_no
		pe.reference_date = frappe.utils.today()
		pe.insert(ignore_permissions=True)
		if pe.docstatus == 0:
			pe.submit()
		return pe.name
	except Exception:
		frappe.log_error(title="SS97 Payment Entry failed", message=frappe.get_traceback())
		return None


def add_invoice_comment(invoice_name: str, content: str) -> None:
	if not invoice_name:
		return
	try:
		frappe.get_doc({
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Sales Invoice",
			"reference_name": invoice_name,
			"content": content,
		}).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="SS97 invoice comment failed", message=frappe.get_traceback())


def get_portal_user_for_customer(customer: str | None) -> str | None:
	if not customer:
		return None
	users = frappe.get_all("Portal User", filters={"parent": customer}, pluck="user", limit=5)
	for user in users:
		if user and user != "Guest":
			return user
	email = frappe.db.get_value("Customer", customer, "email_id")
	if email:
		user = frappe.db.get_value("User", {"email": email, "enabled": 1}, "name")
		if user:
			return user
	return None


def create_client_notification(
	*,
	for_user: str,
	subject: str,
	message: str,
	customer: str | None = None,
	document_type: str | None = None,
	document_name: str | None = None,
) -> None:
	if not for_user or for_user == "Guest":
		return

	if frappe.db.exists("DocType", "SS97 Client Notification"):
		try:
			frappe.get_doc({
				"doctype": "SS97 Client Notification",
				"title": subject,
				"message": message,
				"for_user": for_user,
				"customer": customer,
				"notification_type": "Payment",
				"reference_doctype": document_type,
				"reference_name": document_name,
			}).insert(ignore_permissions=True)
			return
		except Exception:
			frappe.log_error(title="SS97 Client Notification failed", message=frappe.get_traceback())

	try:
		frappe.get_doc({
			"doctype": "Notification Log",
			"subject": subject,
			"email_content": message,
			"for_user": for_user,
			"type": "Alert",
			"document_type": document_type or "Sales Invoice",
			"document_name": document_name or "",
		}).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="SS97 Notification Log failed", message=frappe.get_traceback())


def extract_event_context(event: dict[str, Any]) -> dict[str, Any]:
	obj = event.get("data", {}).get("object") or {}
	event_type = event.get("type") or ""
	livemode = bool(event.get("livemode"))

	amount = 0.0
	currency = (obj.get("currency") or "").upper()
	customer = None

	if obj.get("object") == "checkout.session":
		amount = _amount_from_cents(obj.get("amount_total"))
		customer = obj.get("customer")
	elif obj.get("object") == "payment_intent":
		amount = _amount_from_cents(obj.get("amount_received") or obj.get("amount"))
		customer = obj.get("customer")
	elif obj.get("object") == "invoice":
		amount = _amount_from_cents(obj.get("amount_paid") or obj.get("total"))
		currency = (obj.get("currency") or currency).upper()
		customer = obj.get("customer")
	elif obj.get("object") == "charge":
		amount = _amount_from_cents(obj.get("amount_refunded") or obj.get("amount"))
		customer = obj.get("customer")
	elif obj.get("object") == "subscription":
		customer = obj.get("customer")

	invoice_name = find_sales_invoice_from_stripe_object(obj)
	erp_customer = None
	if invoice_name:
		erp_customer = frappe.db.get_value("Sales Invoice", invoice_name, "customer")
	elif customer and frappe.db.exists("Customer", {"ss97_stripe_customer_id": customer}):
		erp_customer = frappe.db.get_value("Customer", {"ss97_stripe_customer_id": customer}, "name")

	return {
		"object": obj,
		"event_type": event_type,
		"livemode": livemode,
		"amount": amount,
		"currency": currency,
		"invoice": invoice_name,
		"customer": erp_customer,
	}


def is_confirmed_payment(obj: dict[str, Any], event_type: str) -> bool:
	if event_type == "checkout.session.completed":
		return obj.get("payment_status") in SUCCESS_STATUSES or obj.get("status") == "complete"
	if event_type == "payment_intent.succeeded":
		return obj.get("status") == "succeeded"
	if event_type == "invoice.paid":
		return obj.get("status") == "paid" or flt(obj.get("amount_paid")) > 0
	return False


def is_failed_payment(obj: dict[str, Any], event_type: str) -> bool:
	if event_type == "payment_intent.payment_failed":
		return True
	if event_type == "invoice.payment_failed":
		return True
	if event_type == "checkout.session.completed":
		return obj.get("payment_status") in FAILURE_STATUSES
	return False


def process_successful_payment(ctx: dict[str, Any]) -> dict[str, Any]:
	obj = ctx["object"]
	event_type = ctx["event_type"]
	invoice_name = ctx.get("invoice")
	amount = flt(ctx.get("amount"))
	currency = ctx.get("currency")
	customer = ctx.get("customer")

	result: dict[str, Any] = {"invoice": invoice_name, "payment_entry": None}

	if invoice_name:
		ok, warn = verify_amount_currency(invoice_name, amount, currency)
		if not ok:
			result["amount_warning"] = warn

	session_id = obj.get("id") if obj.get("object") == "checkout.session" else obj.get("session") or None
	payment_intent = obj.get("payment_intent") or (
		obj.get("id") if obj.get("object") == "payment_intent" else None
	)
	if isinstance(payment_intent, dict):
		payment_intent = payment_intent.get("id")

	receipt = generate_receipt_ref()
	reference_no = payment_intent or session_id or obj.get("id") or ""

	if invoice_name and is_confirmed_payment(obj, event_type):
		pe = create_payment_entry_for_invoice(invoice_name, amount, reference_no)
		result["payment_entry"] = pe
		update_invoice_stripe_fields(
			invoice_name,
			session_id=session_id if isinstance(session_id, str) else None,
			payment_intent=payment_intent if isinstance(payment_intent, str) else None,
			payment_status="paid",
			receipt_ref=receipt,
			paid_on=str(now_datetime()),
		)
		add_invoice_comment(
			invoice_name,
			f"<p><b>Paiement Stripe confirmé</b> · {receipt} · {event_type}"
			f" · ref {frappe.utils.escape_html(str(reference_no))}</p>",
		)

		portal_user = get_portal_user_for_customer(customer)
		if portal_user:
			create_client_notification(
				for_user=portal_user,
				subject="Paiement accepté SoftSystem97",
				message=f"Paiement confirmé. Reçu {receipt}. Facture {invoice_name}.",
				customer=customer,
				document_type="Sales Invoice",
				document_name=invoice_name,
			)

	result["receipt"] = receipt
	return result


def process_failed_payment(ctx: dict[str, Any]) -> dict[str, Any]:
	obj = ctx["object"]
	invoice_name = ctx.get("invoice")
	result: dict[str, Any] = {"invoice": invoice_name}

	if invoice_name:
		update_invoice_stripe_fields(invoice_name, payment_status="failed")
		add_invoice_comment(
			invoice_name,
			f"<p><b>Paiement Stripe échoué</b> · {ctx['event_type']}</p>",
		)
		customer = ctx.get("customer")
		portal_user = get_portal_user_for_customer(customer)
		if portal_user:
			create_client_notification(
				for_user=portal_user,
				subject="Échec paiement SoftSystem97",
				message=f"Le paiement de la facture {invoice_name} a échoué.",
				customer=customer,
				document_type="Sales Invoice",
				document_name=invoice_name,
			)
	return result


def process_refund(ctx: dict[str, Any]) -> dict[str, Any]:
	obj = ctx["object"]
	invoice_name = ctx.get("invoice")
	result: dict[str, Any] = {"invoice": invoice_name}

	if invoice_name:
		update_invoice_stripe_fields(invoice_name, payment_status="refunded")
		amount = _amount_from_cents(obj.get("amount_refunded"))
		add_invoice_comment(
			invoice_name,
			f"<p><b>Remboursement Stripe</b> · {amount} {ctx.get('currency') or ''}</p>",
		)
	return result


def process_subscription_event(ctx: dict[str, Any]) -> dict[str, Any]:
	obj = ctx["object"]
	sub_id = obj.get("id")
	status = obj.get("status")
	customer = ctx.get("customer")
	result = {"subscription_id": sub_id, "status": status, "customer": customer}

	if customer and sub_id:
		try:
			meta = frappe.get_meta("Customer")
			if meta.has_field("ss97_stripe_subscription_id"):
				frappe.db.set_value(
					"Customer",
					customer,
					"ss97_stripe_subscription_id",
					sub_id,
					update_modified=False,
				)
		except Exception:
			pass

	# Lier à Contract si metadata.contract
	meta = _meta_get(obj)
	contract_name = (meta.get("contract") or "").strip()
	if contract_name and frappe.db.exists("Contract", contract_name):
		try:
			cmeta = frappe.get_meta("Contract")
			if cmeta.has_field("ss97_stripe_subscription_id"):
				frappe.db.set_value(
					"Contract",
					contract_name,
					"ss97_stripe_subscription_id",
					sub_id,
					update_modified=False,
				)
		except Exception:
			pass

	return result


def dispatch_stripe_event(event: dict[str, Any]) -> dict[str, Any]:
	event_type = event.get("type") or ""
	if event_type not in HANDLED_EVENT_TYPES:
		return {"skipped": True, "reason": f"Unhandled event type: {event_type}"}

	ctx = extract_event_context(event)
	obj = ctx["object"]

	if is_confirmed_payment(obj, event_type) or event_type in {
		"checkout.session.completed",
		"payment_intent.succeeded",
		"invoice.paid",
	}:
		if is_confirmed_payment(obj, event_type):
			return process_successful_payment(ctx)
		if is_failed_payment(obj, event_type):
			return process_failed_payment(ctx)
		return {"skipped": True, "reason": "Payment not confirmed"}

	if is_failed_payment(obj, event_type):
		return process_failed_payment(ctx)

	if event_type == "charge.refunded":
		return process_refund(ctx)

	if event_type.startswith("customer.subscription."):
		return process_subscription_event(ctx)

	return {"skipped": True, "reason": "No handler matched"}


def parse_event_payload(raw: bytes) -> dict[str, Any]:
	return json.loads(raw.decode("utf-8"))
