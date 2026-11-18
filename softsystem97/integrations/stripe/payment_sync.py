# -*- coding: utf-8 -*-
"""Helpers Stripe → ERPNext (webhook, sync paiement)."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from decimal import Decimal, InvalidOperation
from typing import Any

import frappe
from frappe.utils import cint, flt, now_datetime
from .settings import setting, config_value, password, assert_accounting_environment, accounting_user

REPLAY_TOLERANCE_SECONDS = 300

FAILURE_STATUSES = frozenset({"failed", "canceled", "payment_failed"})

HANDLED_EVENT_TYPES = frozenset({
	"checkout.session.completed",
	"checkout.session.async_payment_succeeded",
	"checkout.session.async_payment_failed",
	"payment_intent.succeeded",
	"payment_intent.payment_failed",
	"invoice.paid",
	"invoice.payment_failed",
	"customer.subscription.created",
	"customer.subscription.updated",
	"customer.subscription.deleted",
	"charge.refunded",
	"charge.dispute.created",
})


def payments_live_enabled() -> bool:
	return cint(setting("PAYMENTS_LIVE_ENABLED", config_value("payments_live_enabled", 0))) == 1


def stripe_mode() -> str:
	mode = str(setting("STRIPE_MODE") or "").strip().lower()
	if not mode:
		mode = "test" if cint(config_value("test_mode", 1)) == 1 else "live"
	if mode not in ("test", "live"):
		frappe.throw("STRIPE_MODE doit être test ou live.", frappe.PermissionError)
	return mode


def get_webhook_secrets() -> tuple[str | None, str | None]:
	"""Retourne (test_secret, live_secret) sans jamais les logger."""
	return (password("test_webhook_secret", "STRIPE_TEST_WEBHOOK_SECRET"),
		password("webhook_secret", "STRIPE_WEBHOOK_SECRET"))


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

	if timestamp is None or not 0 <= timestamp < 2 ** 63 or not signatures:
		return False

	if abs(time.time() - timestamp) > tolerance:
		return False

	# Sign the original bytes; malformed/non-ASCII signature text must fail closed.
	body = payload if isinstance(payload, bytes) else str(payload).encode("utf-8")
	expected = hmac.new(secret.encode("utf-8"), str(timestamp).encode() + b"." + body, hashlib.sha256).hexdigest()
	return any(len(sig) == 64 and sig.isascii() and hmac.compare_digest(expected, sig) for sig in signatures)


def resolve_webhook_secret(livemode: bool) -> str | None:
	test_secret, live_secret = get_webhook_secrets()
	secret = live_secret if livemode else test_secret
	return secret if secret and secret.startswith("whsec_") else None


def enforce_mode_policy(event: dict[str, Any]) -> None:
	livemode = event.get("livemode")
	if type(livemode) is not bool or livemode != (stripe_mode() == "live"):
		frappe.throw("Événement Stripe incompatible avec STRIPE_MODE.", frappe.PermissionError)
	if not payments_live_enabled() and livemode:
		frappe.throw("Mode LIVE désactivé (PAYMENTS_LIVE_ENABLED=0). Événement rejeté.", frappe.PermissionError)
	if event.get("type") in HANDLED_EVENT_TYPES:
		assert_accounting_environment(livemode)


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
		"result": result or "",
		"error": (error or "")[:500],
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
		frappe.log_error(title="SS97 Stripe Event log failed", message=type(exc).__name__)
		return None


def _meta_get(obj: dict[str, Any]) -> dict[str, Any]:
	return obj.get("metadata") or {}


ZERO_DECIMAL_CURRENCIES = frozenset("BIF CLP DJF GNF JPY KMF KRW MGA PYG RWF VND VUV XAF XOF XPF".split())
THREE_DECIMAL_CURRENCIES = frozenset("BHD JOD KWD OMR TND".split())


def currency_factor(currency):
	code = str(currency or "").upper()
	return 1 if code in ZERO_DECIMAL_CURRENCIES else 1000 if code in THREE_DECIMAL_CURRENCIES else 100


def _amount_from_cents(cents: Any, currency="EUR") -> float:
	if (type(cents) is not int or cents < 0
			or (str(currency).upper() in {"ISK", "UGX"} and cents % 100)):
		frappe.throw("Montant Stripe en unité mineure invalide.", frappe.ValidationError)
	return float(Decimal(cents) / currency_factor(currency))


def minor_units(amount, currency):
	try:
		value = Decimal(str(amount)) * currency_factor(currency)
	except (InvalidOperation, TypeError, ValueError):
		frappe.throw("Montant invalide.", frappe.ValidationError)
	if (not value.is_finite() or value < 0 or value != value.to_integral_value()
			or (str(currency).upper() in {"ISK", "UGX"} and value % 100)):
		frappe.throw("Précision du montant incompatible avec Stripe.", frappe.ValidationError)
	return int(value)


def _stripe_id(value):
	return value.get("id") if isinstance(value, dict) else value


def payment_intent_id(obj):
	value = _stripe_id(obj.get("payment_intent"))
	if obj.get("object") == "payment_intent":
		value = obj.get("id")
	if obj.get("object") == "invoice" and not value and obj.get("status") == "paid":
		# API 2025-03-31+ moved the relation into Invoice Payments.
		payments = (obj.get("payments") or {}).get("data")
		if payments is None:
			from .settings import stripe_client, stripe_call
			payments = stripe_call(stripe_client().v1.invoice_payments.list, {"invoice": obj["id"], "status": "paid"}).data
		paid = [row for row in payments if row.get("status") == "paid"]
		if (len(paid) == 1 and paid[0].get("amount_paid") == obj.get("amount_paid")
				and paid[0].get("currency") == obj.get("currency")):
			value = _stripe_id((paid[0].get("payment") or {}).get("payment_intent"))
	return value if isinstance(value, str) and value.startswith("pi_") else None


def find_sales_invoice_from_stripe_object(obj: dict[str, Any]) -> str | None:
	"""Stored provider relations first; metadata fallback requires customer ownership."""
	kind = obj.get("object")
	links = []
	if kind == "checkout.session":
		links.append(("ss97_stripe_session_id", obj.get("id")))
	elif kind == "invoice":
		links.append(("ss97_stripe_invoice_id", obj.get("id")))
	pi = _stripe_id(obj.get("payment_intent"))
	if kind == "payment_intent":
		pi = obj.get("id")
	if pi:
		links.append(("ss97_stripe_payment_intent", pi))
	bound = set()
	for field, value in links:
		if isinstance(value, str) and value:
			bound.update(frappe.get_all("Sales Invoice", filters={field: value}, pluck="name", limit_page_length=2))
	metadata_name = (_meta_get(obj).get("invoice") or _meta_get(obj).get("erpnext_invoice") or "").strip()
	if len(bound) > 1 or (bound and metadata_name and metadata_name not in bound):
		frappe.throw("Relations facture Stripe contradictoires.", frappe.ValidationError)
	invoice_name = next(iter(bound), None) or metadata_name or None
	if not invoice_name:
		return None  # Another application's Stripe event, explicitly journalled as skipped.
	inv = frappe.db.get_value("Sales Invoice", invoice_name,
		["customer", "ss97_stripe_mode", "ss97_stripe_payment_intent", "ss97_stripe_session_id", "ss97_stripe_invoice_id"], as_dict=True)
	if not inv:
		frappe.throw("Facture Stripe référencée introuvable.", frappe.ValidationError)
	provider_customer = _stripe_id(obj.get("customer"))
	expected_customer = frappe.db.get_value("Customer", inv.customer, "ss97_stripe_customer_id")
	if ((expected_customer and expected_customer != provider_customer and not (kind == "dispute" and bound))
			or (not bound and (not expected_customer or expected_customer != provider_customer))
			or inv.ss97_stripe_mode != stripe_mode()):
		frappe.throw("Client ou environnement Stripe incompatible avec la facture.", frappe.ValidationError)
	for field, value in links:
		if inv.get(field) and inv.get(field) != value:
			frappe.throw("Identifiant Stripe incompatible avec la facture.", frappe.ValidationError)
	return invoice_name


def verify_amount_currency(invoice_name: str, amount: float, currency: str | None) -> tuple[bool, str]:
	if not invoice_name:
		return False, "Facture requise"
	inv = frappe.db.get_value("Sales Invoice", invoice_name,
		["grand_total", "outstanding_amount", "currency"], as_dict=True, for_update=True)
	if not inv or not isinstance(currency, str) or currency.upper() != str(inv.currency).upper():
		return False, "Devise incompatible ou manquante"
	try:
		# No five-cent tolerance; ERPNext must be paid in full in its own currency.
		return (minor_units(amount, currency) == minor_units(inv.outstanding_amount, currency)
			and minor_units(amount, currency) > 0), "Montant divergent"
	except (frappe.ValidationError, TypeError, ValueError):
		return False, "Montant invalide"


def _safe_set_invoice_field(invoice_name: str, fieldname: str, value: Any) -> None:
	if not invoice_name or not value:
		return
	try:
		meta = frappe.get_meta("Sales Invoice")
		if not meta.has_field(fieldname):
			raise frappe.ValidationError("Migration Stripe requise.")
		frappe.db.set_value("Sales Invoice", invoice_name, fieldname, value, update_modified=False)
	except Exception:
		raise frappe.ValidationError("Mise à jour facture Stripe impossible.") from None


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
	return "SS97-RCPT-" + now_datetime().strftime("%Y%m%d%H%M%S") + "-" + frappe.generate_hash(length=8)


def lock_invoice(invoice_name):
	inv = frappe.get_doc("Sales Invoice", invoice_name, for_update=True)
	if inv.docstatus != 1 or inv.is_return or inv.is_pos:
		frappe.throw("Facture soumise non POS requise.", frappe.ValidationError)
	return inv


def create_payment_entry_for_invoice(invoice_name: str, amount: float, reference_no: str) -> str | None:
	"""No commits, permission bypass, direct outstanding updates, or provider fallbacks."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	inv = lock_invoice(invoice_name)
	if flt(inv.outstanding_amount) <= 0:
		return None
	account = config_value("clearing_account")
	bank = frappe.db.get_value("Account", account,
		["company", "account_currency", "account_type", "is_group", "disabled"], as_dict=True) if account else None
	if (not bank or bank.company != inv.company or bank.account_currency != inv.currency
			or bank.account_type != "Bank" or bank.is_group or bank.disabled
			or frappe.db.get_value("Account", inv.debit_to, "account_currency") != inv.currency):
		frappe.throw("Compte de passage Stripe bancaire de même société et devise requis.", frappe.ValidationError)
	transaction_id = stripe_mode() + ":" + reference_no
	# Unique across all invoices, including competing references to the same PI.
	existing = frappe.db.get_value("Payment Entry", {"ss97_stripe_transaction_id": transaction_id},
		["name", "docstatus"], as_dict=True, for_update=True)
	if existing:
		frappe.throw("Transaction Stripe déjà comptabilisée ; rapprochement requis.", frappe.ValidationError)
	with accounting_user():
		pe = get_payment_entry("Sales Invoice", invoice_name, party_amount=amount,
			bank_account=account, bank_amount=amount)
		pe.reference_no = reference_no
		pe.reference_date = frappe.utils.today()
		pe.ss97_stripe_transaction_id = transaction_id
		# Discounts/write-offs are never implicitly accepted by the webhook.
		if (pe.payment_type != "Receive" or pe.party != inv.customer
				or pe.paid_to != account or pe.deductions
				or minor_units(pe.paid_amount, inv.currency) != minor_units(amount, inv.currency)
				or minor_units(pe.received_amount, inv.currency) != minor_units(amount, inv.currency)
				or len(pe.references) != 1 or pe.references[0].reference_name != invoice_name
				or minor_units(pe.references[0].allocated_amount, inv.currency) != minor_units(amount, inv.currency)):
			frappe.throw("Allocation ERPNext incompatible avec Stripe.", frappe.ValidationError)
		pe.insert()
		pe.submit()
	if pe.docstatus != 1:
		frappe.throw("Payment Entry non soumis.", frappe.ValidationError)
	# ERPNext alone updates outstanding; use a current read after its native posting.
	due = frappe.db.get_value("Sales Invoice", invoice_name, "outstanding_amount", for_update=True)
	if minor_units(due, inv.currency) != 0:
		frappe.throw("Facture encore impayée après comptabilisation.", frappe.ValidationError)
	return pe.name


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
	except Exception as exc:
		frappe.log_error(title="SS97 invoice comment failed", message=type(exc).__name__)


def get_portal_user_for_customer(customer: str | None) -> str | None:
	if not customer:
		return None
	from softsystem97.integrations.ticket_bridge.policy import client_customer_for_user

	users = frappe.get_all("Portal User", filters={"parent": customer,
		"parenttype": "Customer", "parentfield": "portal_users"}, pluck="user")
	for user in users:
		if client_customer_for_user(user) == customer:
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
			raise frappe.ValidationError("Notification client non enregistrée.") from None

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
		raise frappe.ValidationError("Notification client non enregistrée.") from None


def extract_event_context(event: dict[str, Any]) -> dict[str, Any]:
	obj = event.get("data", {}).get("object") or {}
	event_type = event.get("type") or ""
	livemode = bool(event.get("livemode"))

	amount = 0.0
	currency = (obj.get("currency") or "").upper()
	customer = None

	if obj.get("object") == "checkout.session":
		amount = _amount_from_cents(obj.get("amount_total", 0), currency)
		customer = obj.get("customer")
	elif obj.get("object") == "payment_intent":
		amount = _amount_from_cents(obj.get("amount_received", 0) if event_type == "payment_intent.succeeded" else obj.get("amount", 0), currency)
		customer = obj.get("customer")
	elif obj.get("object") == "invoice":
		amount = _amount_from_cents(obj.get("amount_paid", 0) if event_type == "invoice.paid" else obj.get("amount_due", 0), currency)
		currency = (obj.get("currency") or currency).upper()
		customer = obj.get("customer")
	elif obj.get("object") == "charge":
		amount = _amount_from_cents(obj.get("amount_refunded", 0), currency)
		customer = obj.get("customer")
	elif obj.get("object") == "subscription":
		customer = obj.get("customer")
	customer = _stripe_id(customer)

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
		"event_created": event.get("created", 0),
		"event_id": event.get("id"),
	}


def is_confirmed_payment(obj: dict[str, Any], event_type: str) -> bool:
	if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
		# Checkout completion also occurs for delayed methods still awaiting payment.
		return obj.get("payment_status") == "paid"
	if event_type == "payment_intent.succeeded":
		return obj.get("status") == "succeeded"
	if event_type == "invoice.paid":
		return obj.get("status") == "paid"
	return False


def is_failed_payment(obj: dict[str, Any], event_type: str) -> bool:
	if event_type in {"payment_intent.payment_failed", "checkout.session.async_payment_failed"}:
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
	if not invoice_name:
		return {"skipped": True, "reason": "No ERPNext invoice binding"}
	if not is_confirmed_payment(obj, event_type):
		frappe.throw("Paiement non confirmé.", frappe.ValidationError)
	assert_accounting_environment(bool(ctx.get("livemode")))
	inv = lock_invoice(invoice_name)
	# Lock before checking outstanding. Distinct event IDs serialize on this invoice.
	if flt(inv.outstanding_amount) <= 0:
		return {"invoice": invoice_name, "payment_entry": None,
			"skipped": True, "reason": "Invoice already settled; review if needed"}
	ok, _ = verify_amount_currency(invoice_name, amount, currency)
	if not ok:
		frappe.throw("Montant ou devise du paiement incompatible avec la facture.", frappe.ValidationError)
	if inv.ss97_payment_status in ("refunded", "refund_pending_review", "disputed"):
		frappe.throw("Paiement bloqué après remboursement ou litige.", frappe.ValidationError)
	session_id = obj.get("id") if obj.get("object") == "checkout.session" else obj.get("session") or None
	payment_intent = payment_intent_id(obj)
	if not payment_intent:
		frappe.throw("PaymentIntent Stripe identifiable requis pour le rapprochement.", frappe.ValidationError)
	if obj.get("object") == "invoice" and obj.get("paid_out_of_band"):
		frappe.throw("Facture Stripe payée hors ligne : rapprochement manuel requis.", frappe.ValidationError)
	receipt = generate_receipt_ref()
	reference_no = payment_intent or session_id or obj.get("id") or ""

	if invoice_name and is_confirmed_payment(obj, event_type):
		# Never announce a paid invoice before ERPNext has a submitted
		# Payment Entry. A provider error must force Stripe to retry.
		outstanding = frappe.db.get_value("Sales Invoice", invoice_name, "outstanding_amount")
		if outstanding is None:
			frappe.throw("État de règlement de la facture indisponible.", frappe.ValidationError)
		if flt(outstanding) <= 0:
			# A second Stripe event may arrive after the first event settled this
			# invoice. Do not create a second entry or send a second receipt.
			# If it was paid elsewhere, do not claim a Stripe settlement.
			return {"invoice": invoice_name, "payment_entry": None,
				"skipped": True, "reason": "Invoice already settled; review if needed"}
		pe = create_payment_entry_for_invoice(invoice_name, amount, reference_no)
		if not pe:
			frappe.throw("Paiement Stripe non comptabilisé : aucune confirmation client.",
				frappe.ValidationError)
		result["payment_entry"] = pe
		update_invoice_stripe_fields(
			invoice_name,
			session_id=session_id if isinstance(session_id, str) else None,
			payment_intent=payment_intent if isinstance(payment_intent, str) else None,
			payment_status="paid",
			mode="live" if ctx.get("livemode") else "test",
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
	invoice_name = ctx.get("invoice")
	result: dict[str, Any] = {"invoice": invoice_name}

	if invoice_name:
		inv = lock_invoice(invoice_name)
		if flt(inv.outstanding_amount) <= 0 or inv.ss97_payment_status in ("paid", "refunded", "refund_pending_review", "disputed"):
			return {"invoice": invoice_name, "skipped": True, "reason": "Stale payment failure"}
		update_invoice_stripe_fields(invoice_name, payment_status="failed", mode="live" if ctx.get("livemode") else "test")
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
	"""Do not cancel a booked receipt or invent a credit note from a charge event."""
	obj, invoice_name = ctx["object"], ctx.get("invoice")
	if not invoice_name:
		return {"skipped": True, "reason": "No ERPNext invoice binding"}
	inv = lock_invoice(invoice_name)
	if str(ctx.get("currency") or "").upper() != str(inv.currency).upper():
		frappe.throw("Devise du remboursement incompatible avec la facture.", frappe.ValidationError)
	amount = _amount_from_cents(obj.get("amount_refunded", 0), ctx.get("currency"))
	if amount <= 0 or obj.get("amount_refunded", 0) > obj.get("amount", 0):
		frappe.throw("Montant remboursé invalide.", frappe.ValidationError)
	update_invoice_stripe_fields(invoice_name, payment_status="refund_pending_review",
		mode="live" if ctx.get("livemode") else "test")
	add_invoice_comment(invoice_name,
		"<p>Remboursement Stripe reçu. Avoir et règlement de remboursement à rapprocher par la comptabilité.</p>")
	portal_user = get_portal_user_for_customer(ctx.get("customer"))
	if portal_user:
		create_client_notification(for_user=portal_user, subject="Remboursement SoftSystem97",
			message=f"Stripe confirme un remboursement de {amount} {ctx.get('currency')}. Facture {invoice_name}.",
			customer=ctx.get("customer"), document_type="Sales Invoice", document_name=invoice_name)
	return {"invoice": invoice_name, "accounting_review_required": True, "amount_refunded": amount}


def process_dispute(ctx):
	invoice_name = ctx.get("invoice")
	if not invoice_name:
		return {"skipped": True, "reason": "No ERPNext invoice binding"}
	lock_invoice(invoice_name)
	update_invoice_stripe_fields(invoice_name, payment_status="disputed")
	return {"invoice": invoice_name, "accounting_review_required": True}


def process_subscription_event(ctx: dict[str, Any]) -> dict[str, Any]:
	obj, customer = ctx["object"], ctx.get("customer")
	if not customer:
		return {"skipped": True, "reason": "No ERPNext customer binding"}
	row = frappe.db.get_value("Customer", customer,
		["ss97_stripe_subscription_id", "ss97_stripe_subscription_status", "ss97_stripe_subscription_event_created"],
		as_dict=True, for_update=True)
	sub_id, status = obj.get("id"), obj.get("status")
	if ctx["event_type"] == "customer.subscription.deleted":
		status = "canceled"
	if row.ss97_stripe_subscription_id and row.ss97_stripe_subscription_id != sub_id:
		frappe.throw("Plusieurs abonnements : rapprochement explicite requis.", frappe.ValidationError)
	if (cint(ctx.get("event_created")) < cint(row.ss97_stripe_subscription_event_created)
			or (row.ss97_stripe_subscription_status == "canceled" and status != "canceled")):
		return {"skipped": True, "reason": "Stale subscription event"}
	frappe.db.set_value("Customer", customer, {
		"ss97_stripe_subscription_id": sub_id,
		"ss97_stripe_subscription_status": status,
		"ss97_stripe_subscription_event_created": cint(ctx.get("event_created")),
	}, update_modified=False)
	contract = (_meta_get(obj).get("contract") or "").strip()
	if contract:
		party = frappe.db.get_value("Contract", contract, ["party_type", "party_name"], as_dict=True)
		if not party or party.party_type != "Customer" or party.party_name != customer:
			frappe.throw("Contrat Stripe incompatible avec le client.", frappe.ValidationError)
		if frappe.get_meta("Contract").has_field("ss97_stripe_subscription_id"):
			bound = frappe.db.get_value("Contract", contract, "ss97_stripe_subscription_id", for_update=True)
			if bound and bound != sub_id:
				frappe.throw("Abonnement du contrat incompatible.", frappe.ValidationError)
			frappe.db.set_value("Contract", contract, "ss97_stripe_subscription_id", sub_id, update_modified=False)
	# Subscription state is informational. It never settles an ERPNext invoice.
	return {"subscription_id": sub_id, "status": status, "customer": customer}


def dispatch_stripe_event(event: dict[str, Any]) -> dict[str, Any]:
	event_type = event.get("type") or ""
	if event_type not in HANDLED_EVENT_TYPES:
		return {"skipped": True, "reason": f"Unhandled event type: {event_type}"}
	# The signed snapshot must match the handler's expected object contract.
	kind = event_type.split(".")[0]
	expected_object = {"checkout": "checkout.session", "customer": "subscription",
		"charge": "dispute" if event_type == "charge.dispute.created" else "charge"}.get(kind, kind)
	if (event.get("data", {}).get("object") or {}).get("object") != expected_object:
		frappe.throw("Objet Stripe incompatible avec le type d'événement.", frappe.ValidationError)

	ctx = extract_event_context(event)
	obj = ctx["object"]

	if is_confirmed_payment(obj, event_type) or event_type in {
		"checkout.session.completed",
		"checkout.session.async_payment_succeeded",
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

	if event_type == "charge.dispute.created":
		return process_dispute(ctx)

	if event_type == "charge.refunded":
		return process_refund(ctx)

	if event_type.startswith("customer.subscription."):
		return process_subscription_event(ctx)

	return {"skipped": True, "reason": "No handler matched"}


def parse_event_payload(raw: bytes) -> dict[str, Any]:
	return json.loads(raw.decode("utf-8"))
