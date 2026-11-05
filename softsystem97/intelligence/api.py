"""Intelligence 360 gated client portal.

Only System Manager can attach a submitted invoice. A completed browser redirect
does not unlock the report; verified Stripe accounting evidence is required.
The feature is disabled by default until the site and the accounting workflow
are reviewed. Never accept financial or status fields from a browser.
"""
import json
from decimal import Decimal
from html import escape

import frappe
from frappe.utils import now_datetime

from .catalog import ALLOWED_STATES, catalog, offer
from .engine import build_assessment, clean_text, parse_answers


def _enabled():
    if frappe.conf.get("ss97_intelligence_enabled") is not True:
        frappe.throw("Intelligence 360 non activé sur ce site.", frappe.PermissionError)


def _client():
    from softsystem97.integrations.ticket_bridge.policy import client_customer_for_user
    user = frappe.session.user
    customer = client_customer_for_user(user)
    if not customer:
        frappe.throw("Compte client non autorisé.", frappe.PermissionError)
    return user, customer


def _staff():
    if frappe.session.user == "Guest":
        frappe.throw("Authentification requise.", frappe.PermissionError)
    frappe.only_for("System Manager")


def _owned(name):
    user, customer = _client()
    if not isinstance(name, str) or len(name) > 140:
        frappe.throw("Dossier inaccessible.", frappe.PermissionError)
    fields = ["name", "customer", "requested_by", "company_name", "sector", "track", "tier",
              "price_eur", "status", "answers_json", "invoice", "report_json",
              "actions_json", "reviewed_by", "reviewed_on", "generated_on"]
    row = frappe.db.get_value("SS97 Intelligence Order", name, fields, as_dict=True)
    if not row or row.customer != customer or row.requested_by != user:
        frappe.throw("Dossier inaccessible.", frappe.PermissionError)
    return row


def _invoice_paid(order):
    """All evidence from DB, not client arguments. Strict single-invoice relation."""
    from softsystem97.integrations.ticket_bridge.payment_gate import (
        invoice_is_fully_stripe_paid, SUCCESS_EVENT_TYPES
    )
    from softsystem97.integrations.stripe.payment_sync import stripe_mode
    from softsystem97.integrations.stripe.settings import is_test_site

    invoice_name = order.invoice
    if not invoice_name:
        return False
    mode = stripe_mode()
    live = mode == "live"
    if not live and not is_test_site():
        return False
    if frappe.db.count("SS97 Intelligence Order", {"invoice": invoice_name}) != 1:
        return False
    inv = frappe.db.get_value("Sales Invoice", invoice_name,
        ["name", "customer", "docstatus", "currency", "grand_total",
         "outstanding_amount", "ss97_payment_status", "ss97_stripe_mode"], as_dict=True)
    if (not inv or inv.customer != order.customer or inv.docstatus != 1
            or inv.currency != "EUR" or inv.ss97_stripe_mode != mode
            or Decimal(str(inv.grand_total)) != Decimal(str(order.price_eur))):
        return False
    if frappe.get_all("SS97 Stripe Event", filters={
        "invoice": invoice_name, "livemode": int(live),
        "event_type": ["in", ["charge.refunded", "charge.dispute.created"]],
        "status": ["in", ["Success", "Pending", "Failed"]],
    }, pluck="name", limit_page_length=1):
        return False
    events = frappe.get_all("SS97 Stripe Event", filters={
        "invoice": invoice_name, "livemode": int(live), "status": "Success",
        "event_type": ["in", list(SUCCESS_EVENT_TYPES)],
    }, fields=["status", "livemode", "event_type", "currency", "result"],
        limit_page_length=100)
    names = set()
    for event in events:
        try:
            result = json.loads(event.result or "")
        except (TypeError, ValueError):
            continue
        if isinstance(result, dict) and isinstance(result.get("payment_entry"), str):
            names.add(result["payment_entry"])
    entries, allocations = {}, {}
    for name in names:
        row = frappe.db.get_value("Payment Entry", name,
            ["docstatus", "payment_type", "party_type", "party"], as_dict=True)
        if row:
            entries[name] = row
            allocations[name] = frappe.get_all("Payment Entry Reference",
                filters={"parent": name, "parenttype": "Payment Entry"},
                fields=["reference_doctype", "reference_name", "allocated_amount"],
                limit_page_length=100)
    return invoice_is_fully_stripe_paid(inv, events, entries, allocations, livemode=live)


def _safe_paid(order):
    try:
        return _invoice_paid(order) is True
    except Exception:
        return False


@frappe.whitelist(methods=["GET"])
def get_catalog():
    _enabled()
    _client()
    return catalog()


@frappe.whitelist(methods=["POST"])
def create_order(company_name, sector, track, tier, answers):
    _enabled()
    user, customer = _client()
    try:
        item = offer(track, tier)
        company_name = clean_text(company_name, 150)
        sector = clean_text(sector, 200)
        clean_answers = parse_answers(answers)
    except ValueError as exc:
        frappe.throw(str(exc), frappe.ValidationError)
    doc = frappe.get_doc({
        "doctype": "SS97 Intelligence Order",
        "customer": customer,
        "requested_by": user,
        "company_name": company_name,
        "sector": sector,
        "track": track,
        "tier": tier,
        "price_eur": item["price_eur"],
        "status": "Draft",
        "answers_json": json.dumps(clean_answers, ensure_ascii=False),
    })
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "status": "Draft", "price_eur": item["price_eur"],
            "currency": "EUR", "next_step": "Facture à rattacher par SS97"}


@frappe.whitelist(methods=["GET"])
def my_orders():
    _enabled()
    user, customer = _client()
    rows = frappe.get_all("SS97 Intelligence Order",
        filters={"customer": customer, "requested_by": user},
        fields=["name", "company_name", "sector", "track", "tier",
                "price_eur", "status", "invoice", "generated_on"],
        order_by="creation desc", limit_page_length=50)
    for row in rows:
        row["payment_verified"] = _safe_paid(row)
        # A client cannot trust a legacy status if payment has been refunded.
        if not row["payment_verified"] and row.status in ("Review", "Delivered"):
            row["status"] = "Payment blocked"
    return rows


@frappe.whitelist(methods=["POST"])
def link_submitted_invoice(order_name, invoice_name):
    """Explicit administrative accounting step; no silent invoice creation."""
    _enabled()
    _staff()
    order = frappe.get_doc("SS97 Intelligence Order", order_name)
    if order.invoice or order.report_json:
        frappe.throw("Facture déjà liée ou rapport existant.", frappe.ValidationError)
    if order.status != "Draft":
        frappe.throw("Dossier non modifiable.", frappe.ValidationError)
    invoice = frappe.db.get_value("Sales Invoice", invoice_name,
        ["customer", "docstatus", "currency", "grand_total", "ss97_payment_status"],
        as_dict=True)
    if (not invoice or invoice.customer != order.customer or invoice.docstatus != 1
            or invoice.currency != "EUR" or invoice.ss97_payment_status in
            ("paid", "refunded", "refund_pending_review", "disputed")
            or Decimal(str(invoice.grand_total)) != Decimal(str(order.price_eur))
            or frappe.db.exists("SS97 Intelligence Order", {"invoice": invoice_name})):
        frappe.throw("Facture soumise unique, impayée et correspondant au montant requise.",
                     frappe.ValidationError)
    order.invoice = invoice_name
    order.status = "Checkout"
    order.save(ignore_permissions=True)
    return {"order": order.name, "invoice": invoice_name}


@frappe.whitelist(methods=["POST"])
def start_checkout(order_name):
    _enabled()
    order = _owned(order_name)
    if not order.invoice or order.status != "Checkout":
        frappe.throw("Facture à préparer par SS97.", frappe.ValidationError)
    if _safe_paid(order):
        return {"paid": True, "message": "Paiement déjà confirmé"}
    from softsystem97.integrations.stripe.checkout import create_invoice_checkout
    # This endpoint itself rechecks Customer ownership, Stripe and accounting state.
    result = create_invoice_checkout(order.invoice)
    return {"paid": False, "checkout_url": result["checkout_url"]}


@frappe.whitelist(methods=["POST"])
def generate_report(order_name):
    _enabled()
    order = _owned(order_name)
    if not _safe_paid(order):
        frappe.throw("Rapport bloqué : règlement non confirmé.", frappe.PermissionError)
    if order.report_json:
        return {"name": order.name, "status": order.status}
    if order.status != "Checkout":
        frappe.throw("Commande indisponible.", frappe.ValidationError)
    doc = frappe.get_doc("SS97 Intelligence Order", order.name)
    if doc.report_json:
        return {"name": doc.name, "status": doc.status}
    try:
        result = build_assessment(doc.company_name, doc.sector, doc.track, doc.tier,
                                  doc.answers_json)
    except ValueError:
        frappe.throw("Questionnaire invalide.", frappe.ValidationError)
    doc.report_json = json.dumps(result, ensure_ascii=False)
    doc.actions_json = json.dumps(result["actions"], ensure_ascii=False)
    doc.generated_on = now_datetime()
    doc.status = "Review" if doc.tier == "expert" else "Delivered"
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist(methods=["POST"])
def approve_expert(order_name):
    _enabled()
    _staff()
    doc = frappe.get_doc("SS97 Intelligence Order", order_name)
    if doc.tier != "expert" or doc.status != "Review" or not doc.report_json:
        frappe.throw("Expertise non prête pour validation.", frappe.ValidationError)
    if not _safe_paid(doc):
        frappe.throw("Paiement non prouvé.", frappe.PermissionError)
    doc.reviewed_by = frappe.session.user
    doc.reviewed_on = now_datetime()
    doc.status = "Delivered"
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist(methods=["GET"])
def report_detail(order_name):
    _enabled()
    order = _owned(order_name)
    if not _safe_paid(order) or order.status != "Delivered" or not order.report_json:
        frappe.throw("Rapport non disponible.", frappe.PermissionError)
    return {"name": order.name, "report": json.loads(order.report_json),
            "actions": json.loads(order.actions_json or "[]"),
            "approved_by_expert": bool(order.reviewed_by)}


@frappe.whitelist(methods=["POST"])
def update_action(order_name, action_id, status):
    _enabled()
    order = _owned(order_name)
    if not _safe_paid(order) or order.status != "Delivered":
        frappe.throw("Projet inaccessible.", frappe.PermissionError)
    if status not in ALLOWED_STATES:
        frappe.throw("Statut invalide.", frappe.ValidationError)
    try:
        action_id = int(action_id)
    except (TypeError, ValueError):
        frappe.throw("Action invalide.", frappe.ValidationError)
    if action_id < 1 or action_id > 12:
        frappe.throw("Action invalide.", frappe.ValidationError)
    doc = frappe.get_doc("SS97 Intelligence Order", order.name)
    actions = json.loads(doc.actions_json or "[]")
    matched = False
    for action in actions:
        if action["id"] == action_id:
            action["status"] = status
            matched = True
    if not matched:
        frappe.throw("Action inconnue.", frappe.ValidationError)
    doc.actions_json = json.dumps(actions, ensure_ascii=False)
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "action_id": action_id, "status": status}


def _html_report(order, report):
    def p(value):
        return escape(str(value if value is not None else ""))
    rows = "".join("<tr><td>" + p(a["id"]) + "</td><td>" + p(a["theme"]) +
                   "</td><td>" + p(a["action"]) + "</td><td>" +
                   p(a["horizon_jours"]) + " jours</td></tr>" for a in report["actions"])
    notes = "".join("<li>" + p(x) + "</li>" for x in report["limitations"])
    scenarios = ""
    if report.get("scenarios"):
        s = report["scenarios"]
        scenarios = "<h2>Scénarios indicatifs à 36 mois</h2><p>" + p(s["warning"]) + "</p>"
        scenarios += "<ul>" + "".join("<li>" + p(x["label"]) + " : " +
            p(x["ca_annee_3"]) + " EUR de CA hypothétique</li>" for x in s["scenarios"]) + "</ul>"
    return (
        '<html><head><meta charset="utf-8"><style>'
        'body{font-family:Arial,sans-serif;font-size:11px;color:#173044}'
        'h1{font-size:22px}h2{font-size:15px;margin-top:24px}'
        'table{width:100%;border-collapse:collapse}th,td{border:1px solid #cbd5df;padding:8px;text-align:left}'
        'th{background:#eaf1f7} .small{color:#526578}</style></head><body>'
        '<h1>Soft System 97 — Intelligence 360</h1>'
        '<p class="small">Rapport privé ' + p(order.name) + ' — ' +
        p(order.generated_on) + '</p><h2>' + p(report["company_name"]) + '</h2>'
        '<p>Secteur : ' + p(report["sector"]) + ' | Programme : ' +
        p(report["track"]) + ' | Niveau : ' + p(report["tier"]) + '</p>'
        '<h2>Objectif déclaré</h2><p>' + p(report["objective_declared"]) + '</p>'
        '<h2>Difficultés déclarées</h2><p>' + p(report["challenges_declared"]) + '</p>'
        '<h2>Points forts déclarés</h2><p>' + p(report["strengths_declared"]) + '</p>'
        '<p>Complétude des données : ' + p(report["data_completeness_pct"]) + '%'
        ' — cet indicateur ne mesure pas la santé de l’entreprise.</p>'
        '<h2>Plan d’action</h2><table><thead><tr><th>№</th><th>Domaine</th>'
        '<th>Recommandation</th><th>Échéance</th></tr></thead><tbody>' +
        rows + '</tbody></table>' + scenarios +
        '<h2>Portée et limites</h2><ul>' + notes + '</ul>'
        '<p>Les recommandations demandent une vérification avant exécution.</p>'
        '</body></html>'
    )


@frappe.whitelist(methods=["GET"])
def download_pdf(order_name):
    _enabled()
    order = _owned(order_name)
    if not _safe_paid(order) or order.status != "Delivered" or not order.report_json:
        frappe.throw("PDF inaccessible.", frappe.PermissionError)
    from frappe.utils.pdf import get_pdf
    pdf = get_pdf(_html_report(order, json.loads(order.report_json)))
    frappe.local.response.filename = "SS97-Intelligence-" + order.name + ".pdf"
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "download"
    frappe.local.response.headers = frappe.local.response.get("headers") or {}
    frappe.local.response.headers["Cache-Control"] = "no-store, private"
