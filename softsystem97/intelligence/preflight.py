"""Read-only preflight for deploying Intelligence 360 on a Frappe/ERPNext site.

Run in an already-installed app environment, e.g.
  bench --site audit.localhost execute softsystem97.intelligence.preflight.inspect

Never reports secrets, keys, file content, customers, account numbers, or user emails.
This is observational only; it cannot prove a real Stripe payment or remote help.
"""
from __future__ import annotations


def inspect():
    import frappe

    checks = []
    def add(key, ok, action):
        checks.append({"id": key, "ok": bool(ok), "action_if_failed": action if not ok else ""})

    installed = set(frappe.get_installed_apps() or [])
    add("frappe_app_installed", "softsystem97" in installed,
        "Installer l'application SoftSystem97 sur le site.")
    add("erpnext_installed", "erpnext" in installed,
        "Installer ERPNext pour la comptabilité native.")
    for doctype in ("Customer", "Sales Invoice", "Payment Entry",
                    "SS97 Intelligence Order", "SS97 Intelligence Mission",
                    "SS97 Stripe Config", "SS97 Stripe Event"):
        add("doctype_" + doctype.lower().replace(" ", "_"),
            bool(frappe.db.exists("DocType", doctype)),
            "Déployer la branche puis mettre à jour le schéma du site.")

    try:
        si = frappe.get_meta("Sales Invoice")
        invoice_fields = ("ss97_stripe_session_id", "ss97_payment_status", "ss97_stripe_mode")
        add("stripe_invoice_fields", all(si.has_field(k) for k in invoice_fields),
            "Vérifier l'installation du patch comptable Stripe et ses champs.")
    except Exception:
        add("stripe_invoice_fields", False, "Métadonnées Sales Invoice indisponibles.")

    enabled = frappe.conf.get("ss97_intelligence_enabled") is True
    auto = frappe.conf.get("ss97_intelligence_auto_invoice") is True
    add("intelligence_feature_enabled", enabled,
        "N'activer que lorsque la recette sur site isolé est réussie.")
    add("automatic_invoice_opt_in", auto,
        "Après validation de la facturation fiscale, activer le flag sur le site isolé.")

    configured = False
    tax_verified = False
    try:
        from .billing_rules import validate_billing_settings
        from .billing import _validate_master_data
        raw = frappe.conf.get("ss97_intelligence_billing")
        config = validate_billing_settings(dict(raw) if isinstance(raw, dict) else raw)
        configured = True
        try:
            _validate_master_data(config)
            tax_verified = True
        except Exception:
            tax_verified = False
    except Exception:
        configured = False
    add("billing_config_valid", configured,
        "Définir Company, Item et modèle fiscal explicite dans site_config.")
    add("accounting_master_data_valid", tax_verified,
        "Vérifier Company EUR, Item de service et TVA TTC dans ERPNext.")

    try:
        from softsystem97.integrations.stripe.payment_sync import stripe_mode, payments_live_enabled
        from softsystem97.integrations.stripe.settings import is_test_site
        mode = stripe_mode()
        valid_env = (mode == "live" and payments_live_enabled()) or (mode == "test" and is_test_site())
    except Exception:
        mode, valid_env = "unknown", False
    add("stripe_mode_allowed", valid_env,
        "Site isolé en TEST ou LIVE explicitement activé après recette; jamais de mode mélangé.")

    try:
        from softsystem97.integrations.stripe.settings import config_value
        has_account = bool(config_value("clearing_account") and config_value("service_user"))
    except Exception:
        has_account = False
    add("stripe_accounting_settings_present", has_account,
        "Configurer et vérifier le compte de passage et le compte de service Stripe.")

    # Route source is not proof of correct HTTP routing nor source deployment;
    # HTTP + cross-tenant tests are mandatory after app update.
    return {
        "component": "SS97 Intelligence 360",
        "scope": "read_only_preflight",
        "site": str(frappe.local.site),
        "stripe_mode": mode,
        "checks": checks,
        "ready_for_live": False,
        "warning": ("Aucun test HTTPS réel, aucun paiement signé, aucune preuve de TVA "
                    "et aucun test inter-clients n'est effectué par ce diagnostic."),
    }
