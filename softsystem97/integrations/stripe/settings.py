"""Server-only Stripe settings. No credential is returned through an HTTP API."""
from contextlib import contextmanager
import os

import frappe
from frappe.utils import cint


def setting(name, default=None):
    value = frappe.conf.get(name)
    return os.environ.get(name, default) if value is None else value


def config_value(field, default=None):
    if not frappe.db.exists("DocType", "SS97 Stripe Config"):
        return default
    value = frappe.db.get_single_value("SS97 Stripe Config", field)
    return default if value is None else value


def password(field, variable):
    # Explicit site/environment configuration takes precedence over the Single.
    value = setting(variable)
    if value:
        return str(value).strip()
    if frappe.db.exists("DocType", "SS97 Stripe Config"):
        value = frappe.get_single("SS97 Stripe Config").get_password(field, raise_exception=False)
    return str(value).strip() if value else None


def is_test_site():
    return (setting("ss97_stripe_test_site") is True
            and cint(frappe.conf.get("allow_tests")) == 1
            and frappe.local.site != "app.softsystem97.com")


def assert_accounting_environment(livemode):
    if not livemode and not is_test_site():
        frappe.throw("Écritures Stripe TEST interdites hors site de test isolé.", frappe.PermissionError)


@contextmanager
def accounting_user():
    """Use an explicit least-privilege account; restore the HTTP actor on all paths."""
    user = config_value("service_user")
    if (not user or user in ("Guest", "Administrator")
            or not frappe.db.get_value("User", user, "enabled")
            or not {"Accounts User", "Accounts Manager"}.intersection(frappe.get_roles(user))):
        frappe.throw("Utilisateur de service comptable Stripe requis.", frappe.PermissionError)
    previous = frappe.session.user
    previous_sid = frappe.session.get("sid")
    previous_data = frappe.session.get("data")
    previous_form = getattr(frappe.local, "form_dict", None)
    try:
        frappe.set_user(user)
        yield
    finally:
        frappe.set_user(previous)
        frappe.session.sid = previous_sid
        frappe.session.data = previous_data
        if previous_form is not None:
            frappe.local.form_dict = previous_form


def stripe_client():
    from .payment_sync import payments_live_enabled, stripe_mode

    live = stripe_mode() == "live"
    if live and not payments_live_enabled():
        frappe.throw("Paiements LIVE désactivés.", frappe.PermissionError)
    key = password("live_secret_key" if live else "test_secret_key",
                   "STRIPE_SECRET_KEY" if live else "STRIPE_TEST_SECRET_KEY")
    prefixes = ("sk_live_", "rk_live_") if live else ("sk_test_", "rk_test_")
    if not key or not key.startswith(prefixes):
        frappe.throw("Clé API Stripe du mode actif requise (distincte du secret webhook).",
                     frappe.ValidationError)
    from stripe import StripeClient, RequestsClient
    # Keep the snapshot contract already configured for this existing integration.
    return StripeClient(key, stripe_version="2026-06-24.dahlia", max_network_retries=2,
                        http_client=RequestsClient())


def stripe_call(method, *args, **kwargs):
    try:
        return method(*args, **kwargs)
    except Exception:
        # Provider error text can contain credential fragments. Drop its context.
        raise frappe.ValidationError("Opération Stripe indisponible ; vérifier la configuration et les permissions.") from None
