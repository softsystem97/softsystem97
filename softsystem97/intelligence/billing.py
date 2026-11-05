"""Automatic ERPNext Sales Invoice creation for paid Intelligence assessments.

Disabled by default and guarded by explicit site configuration. All financial
data is resolved server-side. The client can request purchase but cannot pick
a tax, revenue account, Item, Company or currency. Invoice validation and posting
use the same least-privilege accounting service account as Stripe.
"""
from decimal import Decimal

import frappe
from frappe.utils import today

from .billing_rules import exact_eur, validate_billing_settings, validate_inclusive_taxes
from .catalog import offer


def _settings():
    if frappe.conf.get("ss97_intelligence_auto_invoice") is not True:
        frappe.throw("Facturation automatique non activée.", frappe.PermissionError)
    settings = frappe.conf.get("ss97_intelligence_billing")
    try:
        # Frappe _dict subclasses dict. Copy to avoid mutating settings.
        return validate_billing_settings(dict(settings) if isinstance(settings, dict) else settings)
    except ValueError:
        frappe.throw("Paramétrage comptable incomplet : contacter SS97.", frappe.ValidationError)


def _validate_master_data(settings):
    company = frappe.db.get_value("Company", settings["company"],
        ["name", "default_currency"], as_dict=True)
    item = frappe.db.get_value("Item", settings["item_code"],
        ["item_code", "disabled", "is_stock_item", "is_sales_item", "has_variants"],
        as_dict=True)
    if not company or company.default_currency != "EUR":
        frappe.throw("Société ERPNext en EUR obligatoire.", frappe.ValidationError)
    if (not item or item.disabled or item.is_stock_item
            or not item.is_sales_item or item.has_variants):
        frappe.throw("Article de service valide requis.", frappe.ValidationError)

    if settings.get("income_account"):
        account = frappe.db.get_value("Account", settings["income_account"],
            ["company", "disabled", "is_group"], as_dict=True)
        if (not account or account.company != company.name or account.disabled or account.is_group):
            frappe.throw("Compte de produits incompatible.", frappe.ValidationError)
    if settings.get("cost_center"):
        cc = frappe.db.get_value("Cost Center", settings["cost_center"],
            ["company", "disabled", "is_group"], as_dict=True)
        if not cc or cc.company != company.name or cc.disabled or cc.is_group:
            frappe.throw("Centre de coûts incompatible.", frappe.ValidationError)

    template = None
    if not settings.get("tax_exempt"):
        template = frappe.get_doc("Sales Taxes and Charges Template", settings["tax_template"])
        if template.company != company.name or template.disabled:
            frappe.throw("Modèle fiscal de société invalide.", frappe.ValidationError)
        try:
            validate_inclusive_taxes([{
                "charge_type": r.charge_type, "included_in_print_rate": r.included_in_print_rate,
                "add_deduct_tax": r.add_deduct_tax, "account_head": r.account_head
            } for r in template.taxes])
        except ValueError:
            frappe.throw("Modèle de TVA non compatible avec un prix TTC.", frappe.ValidationError)
    return company, item, template


def _copy_taxes(invoice, template):
    if not template:
        return
    invoice.taxes_and_charges = template.name
    # Explicit copy of reviewed template rows, no tax rate guessed by SS97.
    for tax in template.taxes:
        invoice.append("taxes", {
            "charge_type": tax.charge_type,
            "account_head": tax.account_head,
            "description": tax.description,
            "rate": tax.rate,
            "included_in_print_rate": tax.included_in_print_rate,
            "add_deduct_tax": tax.add_deduct_tax or "Add",
            "row_id": tax.row_id,
            "cost_center": tax.cost_center,
        })


def ensure_submitted_invoice(order_name, customer, requested_by):
    """One transaction, row-locked order; call only after customer ownership check."""
    from softsystem97.integrations.stripe.payment_sync import stripe_mode
    from softsystem97.integrations.stripe.settings import accounting_user

    config = _settings()
    # Exclusive DB row lock prevents two invoices for simultaneous clicks.
    order = frappe.db.get_value("SS97 Intelligence Order", order_name,
        ["name", "customer", "requested_by", "company_name", "tier", "track",
         "price_eur", "status", "invoice"], as_dict=True, for_update=True)
    if not order or order.customer != customer or order.requested_by != requested_by:
        frappe.throw("Dossier inaccessible.", frappe.PermissionError)
    if order.invoice:
        if order.status != "Checkout":
            frappe.throw("Facture déjà liée à un autre état.", frappe.ValidationError)
        return order.invoice
    if order.status != "Draft":
        frappe.throw("Dossier non facturable.", frappe.ValidationError)

    expected = exact_eur(offer(order.track, order.tier)["price_eur"])
    if expected != exact_eur(order.price_eur):
        frappe.throw("Tarif du dossier incompatible avec le catalogue.", frappe.ValidationError)
    company, item, template = _validate_master_data(config)

    # Protect the order's customer from the same name being reused improperly.
    if frappe.db.count("SS97 Intelligence Order", {"customer": customer,
             "requested_by": requested_by, "status": "Checkout", "invoice": ["!=", ""]}) > 20:
        frappe.throw("Trop de factures en attente ; contacter SS97.", frappe.ValidationError)

    fields = {
        "doctype": "Sales Invoice",
        "company": company.name,
        "customer": order.customer,
        "currency": "EUR",
        "posting_date": today(),
        "due_date": today(),
        "is_pos": 0,
        "items": [{
            "item_code": item.item_code, "qty": 1, "rate": float(expected),
            "description": f"SS97 Intelligence 360 — {order.track} — {order.tier} — {order.name}",
            **({"income_account": config["income_account"]} if config.get("income_account") else {}),
            **({"cost_center": config["cost_center"]} if config.get("cost_center") else {}),
        }],
        "ss97_stripe_mode": stripe_mode(),
        "ss97_payment_status": "pending",
    }
    with accounting_user():
        invoice = frappe.get_doc(fields)
        _copy_taxes(invoice, template)
        invoice.insert()
        # ERPNext calculates taxes natively; reject unexpected extra charges.
        if (invoice.currency != "EUR"
                or exact_eur(invoice.grand_total) != expected
                or invoice.customer != customer or invoice.company != company.name
                or invoice.is_pos):
            frappe.throw("Total facture TTC différent du prix du catalogue.", frappe.ValidationError)
        invoice.submit()
    if (invoice.docstatus != 1 or exact_eur(invoice.grand_total) != expected):
        frappe.throw("Facture non soumise ou montant incohérent.", frappe.ValidationError)

    # The transaction must roll back invoice AND order on any failure.
    doc = frappe.get_doc("SS97 Intelligence Order", order_name)
    doc.invoice = invoice.name
    doc.status = "Checkout"
    doc.save(ignore_permissions=True)
    return invoice.name
