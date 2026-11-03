"""Customer-owned Checkout for existing, submitted ERPNext invoices."""
from urllib.parse import urljoin, urlparse

import frappe

from .payment_sync import lock_invoice, minor_units, stripe_mode, update_invoice_stripe_fields
from .settings import assert_accounting_environment, config_value, stripe_client, stripe_call


def _return_url(field):
    base = frappe.utils.get_url()
    url = urljoin(base + "/", config_value(field) or "/espace-client/paiements")
    if urlparse(url).scheme != "https" or urlparse(url).netloc != urlparse(base).netloc:
        frappe.throw("URL de retour Stripe HTTPS du site requise.", frappe.ValidationError)
    return url


@frappe.whitelist(methods=["POST"])
def create_invoice_checkout(invoice):
    from softsystem97.integrations.ticket_bridge.policy import client_customer_for_user

    user = frappe.session.user
    customer = client_customer_for_user(user)
    technician_role = (frappe.conf.get("ss97_ticket_bridge") or {}).get("technician_role", "SS97 Technician")
    if not customer or technician_role in frappe.get_roles(user):
        frappe.throw("Accès paiement client refusé.", frappe.PermissionError)
    # Do not reveal another customer's invoice or hold its lock.
    if not isinstance(invoice, str) or frappe.db.get_value("Sales Invoice", invoice, "customer") != customer:
        frappe.throw("Facture inaccessible.", frappe.PermissionError)
    live = stripe_mode() == "live"
    assert_accounting_environment(live)
    inv = lock_invoice(invoice)
    amount = minor_units(inv.outstanding_amount, inv.currency)
    if amount <= 0 or inv.ss97_payment_status in ("refunded", "refund_pending_review", "disputed"):
        frappe.throw("Facture indisponible pour paiement.", frappe.ValidationError)
    client = stripe_client()
    provider_customer = frappe.db.get_value("Customer", customer, "ss97_stripe_customer_id", for_update=True)
    if not provider_customer:
        # Stable idempotency keys survive a database rollback after a network call.
        result = stripe_call(client.v1.customers.create, {"metadata": {"erpnext_customer": customer}},
            options={"idempotency_key": f"ss97:customer:{frappe.local.site}:{stripe_mode()}:{customer}"})
        provider_customer = result.id
        frappe.db.set_value("Customer", customer, "ss97_stripe_customer_id", provider_customer, update_modified=False)
    if inv.ss97_stripe_session_id:
        session = stripe_call(client.v1.checkout.sessions.retrieve, inv.ss97_stripe_session_id)
        if session.status == "open" and session.amount_total == amount and session.currency.upper() == inv.currency.upper():
            return {"invoice": invoice, "checkout_url": session.url, "session_id": session.id}
        if session.status == "complete":
            frappe.throw("Paiement en cours de rapprochement. Rechargez la facture.", frappe.ValidationError)
        # Expired/canceled sessions require an explicit accounting review; do not
        # overwrite the old PI relation while a delayed event can still arrive.
        frappe.throw("Session Stripe expirée : renouvellement à vérifier par le support.", frappe.ValidationError)
    session = stripe_call(client.v1.checkout.sessions.create, {
        "mode": "payment", "customer": provider_customer,
        "client_reference_id": invoice, "metadata": {"invoice": invoice},
        "payment_intent_data": {"metadata": {"invoice": invoice}},
        "line_items": [{"price_data": {"currency": inv.currency.lower(), "unit_amount": amount,
            "product_data": {"name": "Facture SoftSystem97 " + invoice}}, "quantity": 1}],
        "success_url": _return_url("success_url"), "cancel_url": _return_url("cancel_url"),
    }, options={"idempotency_key": f"ss97:checkout:{frappe.local.site}:{stripe_mode()}:{invoice}:{amount}:{inv.currency}"})
    update_invoice_stripe_fields(invoice, session_id=session.id, mode=stripe_mode(), payment_status="pending")
    frappe.db.set_value("Sales Invoice", invoice, "ss97_stripe_checkout_url", session.url, update_modified=False)
    return {"invoice": invoice, "checkout_url": session.url, "session_id": session.id}


def _ticket_for_actor(issue, *, client_only=False):
    from softsystem97.integrations.ticket_bridge import policy
    if not isinstance(issue, str) or not issue:
        frappe.throw("Ticket inaccessible.", frappe.PermissionError)
    doc = frappe.get_doc("Issue", issue)
    customer = policy.client_customer_for_user(frappe.session.user)
    if customer and doc.customer == customer and doc.raised_by == frappe.session.user:
        return doc
    if not client_only:
        if "System Manager" in frappe.get_roles(frappe.session.user):
            return doc
        policy.authorize(doc, "technician")
        return doc
    frappe.throw("Ticket inaccessible.", frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
def create_ticket_checkout(issue):
    doc = _ticket_for_actor(issue, client_only=True)
    invoices = frappe.get_all("Sales Invoice", filters={"ss97_linked_issue": doc.name, "docstatus": 1},
        pluck="name", limit_page_length=2)
    if len(invoices) != 1:
        frappe.throw("Une facture soumise unique doit être reliée au ticket.", frappe.ValidationError)
    return create_invoice_checkout(invoices[0])


@frappe.whitelist(methods=["GET", "POST"])
def get_ticket_payment_status(issue):
    from softsystem97.integrations.ticket_bridge.payment_gate import issue_has_verified_stripe_payment
    doc = _ticket_for_actor(issue)
    return {"issue": doc.name, "ok": issue_has_verified_stripe_payment(doc.name) is True}
