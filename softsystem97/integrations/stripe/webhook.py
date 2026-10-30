# -*- coding: utf-8 -*-
"""Webhook Stripe entrant pour SoftSystem97.

API endpoint (POST, guest autorisé) :
  /api/method/softsystem97.integrations.stripe.webhook.stripe_webhook

Alias équivalent :
  /api/method/softsystem97.integrations.stripe.webhook.webhook
"""
from __future__ import annotations

import frappe
from frappe import _

from softsystem97.integrations.stripe.payment_sync import (
	dispatch_stripe_event,
	enforce_mode_policy,
	event_already_processed,
	log_stripe_event,
	parse_event_payload,
	resolve_webhook_secret,
	verify_stripe_signature,
)


def _get_raw_body() -> bytes:
	request = frappe.local.request
	if request is None:
		return b""
	data = getattr(request, "data", None)
	if data is None:
		data = getattr(request, "get_data", lambda cache=True, as_text=False: b"")(cache=False, as_text=False)
	if isinstance(data, str):
		return data.encode("utf-8")
	return data or b""


def _reject(message: str, http_status_code: int = 403) -> None:
	frappe.local.response["http_status_code"] = http_status_code
	try:
		frappe.throw(_(message), exc=frappe.PermissionError)
	except frappe.PermissionError as rejection:
		raise rejection from None  # Do not chain a sensitive upstream exception.


def _lock_event(event_id: str, event_type: str, livemode: bool):
	"""Claim an existing unique event under the request transaction, never commit.

	A concurrent first insert may deadlock/lose the unique-key race: let the HTTP
	boundary roll back and Stripe retry. Never dispatch without a locked receipt.
	"""
	if not frappe.db.exists("DocType", "SS97 Stripe Event"):
		_reject("Journal Stripe indisponible ; migration requise", 503)
	row = frappe.db.get_value("SS97 Stripe Event", {"stripe_event_id": event_id},
		["name", "status"], as_dict=True, for_update=True)
	if row:
		return row  # Current locking read, not a repeatable-read snapshot.
	doc = frappe.get_doc(dict(doctype="SS97 Stripe Event", stripe_event_id=event_id,
		event_type=event_type, event_date=frappe.utils.now_datetime(),
		status="Pending", livemode=int(livemode))).insert(ignore_permissions=True)
	return frappe._dict(name=doc.name, status=doc.status)


def _handle_stripe_webhook() -> dict:
	raw = _get_raw_body()
	if not raw:
		_reject("Corps de requête vide", 400)

	sig_header = ""
	request = frappe.local.request
	if request:
		sig_header = request.headers.get("Stripe-Signature") or request.headers.get("stripe-signature") or ""

	try:
		event = parse_event_payload(raw)
	except Exception:
		_reject("Payload JSON invalide", 400)
	if not isinstance(event, dict):
		_reject("Objet événement Stripe requis", 400)

	stripe_event_id = event.get("id") or ""
	event_type = event.get("type") or ""
	livemode = bool(event.get("livemode"))
	if (not isinstance(stripe_event_id, str) or not stripe_event_id
			or len(stripe_event_id) > 140 or not isinstance(event_type, str)
			or not event_type or len(event_type) > 140):
		_reject("Identité événement Stripe invalide", 400)

	secret = resolve_webhook_secret(livemode)
	if not secret:
		_reject("Secret webhook Stripe non configuré", 403)

	if not verify_stripe_signature(raw, sig_header, secret):
		_reject("Signature Stripe invalide", 403)

	# Even a replay must be authenticated before revealing/acknowledging an event.
	if event_already_processed(stripe_event_id):
		return {"ok": True, "duplicate": True, "event_id": stripe_event_id}

	try:
		enforce_mode_policy(event)
	except frappe.PermissionError as exc:
		log_stripe_event(
			stripe_event_id,
			event_type,
			status="Failed",
			error=str(exc),
			livemode=livemode,
		)
		frappe.db.commit()
		_reject(str(exc), 403)

	claim = _lock_event(stripe_event_id, event_type, livemode)
	if claim.status == "Success":
		return {"ok": True, "duplicate": True, "event_id": stripe_event_id}

	ctx_preview = {"customer": None, "invoice": None, "amount": None, "currency": None}
	try:
		from softsystem97.integrations.stripe.payment_sync import extract_event_context

		ctx_preview = extract_event_context(event)
	except Exception:
		pass

	log_name = log_stripe_event(
		stripe_event_id,
		event_type,
		customer=ctx_preview.get("customer"),
		invoice=ctx_preview.get("invoice"),
		amount=ctx_preview.get("amount"),
		currency=ctx_preview.get("currency"),
		status="Pending",
		livemode=livemode,
	)
	if not log_name:
		_reject("Journalisation Stripe indisponible", 503)

	try:
		result = dispatch_stripe_event(event)
		completed_log = log_stripe_event(
			stripe_event_id,
			event_type,
			customer=ctx_preview.get("customer"),
			invoice=ctx_preview.get("invoice") or result.get("invoice"),
			amount=ctx_preview.get("amount"),
			currency=ctx_preview.get("currency"),
			status="Success",
			result=frappe.as_json(result) if result else "OK",
			livemode=livemode,
		)
		if not completed_log:
			raise frappe.ValidationError("Journalisation Stripe non confirmée")
		frappe.db.commit()
		return {"ok": True, "event_id": stripe_event_id, "type": event_type, "result": result, "log": log_name}
	except Exception as exc:
		frappe.db.rollback()
		# Reclaim after rollback: a concurrent successful retry must never be
		# overwritten by this request's failure receipt.
		failure_claim = _lock_event(stripe_event_id, event_type, livemode)
		if failure_claim.status != "Success":
			log_stripe_event(
				stripe_event_id,
				event_type,
				customer=ctx_preview.get("customer"),
				invoice=ctx_preview.get("invoice"),
				amount=ctx_preview.get("amount"),
				currency=ctx_preview.get("currency"),
				status="Failed",
				error=type(exc).__name__,
				livemode=livemode,
			)
		frappe.db.commit()
		frappe.log_error(title="SS97 Stripe webhook failed", message=type(exc).__name__)
		_reject("Erreur traitement webhook", 500)


class StripeRetryConflict(frappe.ValidationError):
	http_status_code = 409


def _handle_with_retry_response():
	try:
		return _handle_stripe_webhook()
	except (frappe.QueryDeadlockError, frappe.QueryTimeoutError,
			frappe.DuplicateEntryError, frappe.UniqueValidationError):
		# Let the HTTP boundary roll back. A fresh signed delivery may retry;
		# never acknowledge success while another transaction owns the receipt.
		raise StripeRetryConflict("Événement en concurrence ; réessayez la livraison.") from None


@frappe.whitelist(allow_guest=True, methods=["POST"])
def stripe_webhook() -> dict:
	"""Point d'entrée webhook Stripe (signature + idempotence)."""
	return _handle_with_retry_response()


@frappe.whitelist(allow_guest=True, methods=["POST"])
def webhook() -> dict:
	"""Alias de stripe_webhook."""
	return _handle_with_retry_response()
