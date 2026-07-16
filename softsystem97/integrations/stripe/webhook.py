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
	frappe.throw(_(message), exc=frappe.PermissionError)


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

	stripe_event_id = event.get("id") or ""
	event_type = event.get("type") or ""
	livemode = bool(event.get("livemode"))

	if event_already_processed(stripe_event_id):
		return {"ok": True, "duplicate": True, "event_id": stripe_event_id}

	secret = resolve_webhook_secret(livemode)
	if not secret:
		_reject("Secret webhook Stripe non configuré", 403)

	if not verify_stripe_signature(raw, sig_header, secret):
		_reject("Signature Stripe invalide", 403)

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

	try:
		result = dispatch_stripe_event(event)
		log_stripe_event(
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
		frappe.db.commit()
		return {"ok": True, "event_id": stripe_event_id, "type": event_type, "result": result, "log": log_name}
	except Exception as exc:
		frappe.db.rollback()
		log_stripe_event(
			stripe_event_id,
			event_type,
			customer=ctx_preview.get("customer"),
			invoice=ctx_preview.get("invoice"),
			amount=ctx_preview.get("amount"),
			currency=ctx_preview.get("currency"),
			status="Failed",
			error=str(exc)[:500],
			livemode=livemode,
		)
		frappe.db.commit()
		frappe.log_error(title=f"SS97 Stripe webhook {event_type}", message=frappe.get_traceback())
		_reject("Erreur traitement webhook", 500)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def stripe_webhook() -> dict:
	"""Point d'entrée webhook Stripe (signature + idempotence)."""
	return _handle_stripe_webhook()


@frappe.whitelist(allow_guest=True, methods=["POST"])
def webhook() -> dict:
	"""Alias de stripe_webhook."""
	return _handle_stripe_webhook()
