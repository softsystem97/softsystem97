"""Pure validations for tax-safe, fail-closed SS97 Intelligence invoicing.

No branch may guess tax rates or allow a generic digital service to become
a stock item. The ERPNext invoice remains the accounting source of truth.
"""
from decimal import Decimal, InvalidOperation


def exact_eur(value):
    if isinstance(value, bool):
        raise ValueError("Montant invalide")
    try:
        amount = Decimal(str(value))
    except (TypeError, InvalidOperation, ValueError) as exc:
        raise ValueError("Montant invalide") from exc
    if not amount.is_finite() or amount <= 0 or amount > Decimal("1000000"):
        raise ValueError("Montant hors limites")
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Montant de précision invalide")
    return amount


def validate_billing_settings(settings):
    """Untrusted-in-web, trusted-in-site_config contract; no secret parameters."""
    if not isinstance(settings, dict):
        raise ValueError("Configuration de facturation indisponible")
    allowed = {"company", "item_code", "tax_template", "tax_exempt",
               "income_account", "cost_center"}
    if set(settings) - allowed:
        raise ValueError("Configuration avec clés inconnues")
    for key in ("company", "item_code"):
        if not isinstance(settings.get(key), str) or not settings[key].strip():
            raise ValueError(f"Configuration {key} manquante")
    exempt = settings.get("tax_exempt") is True
    template = settings.get("tax_template")
    if exempt:
        if template:
            raise ValueError("Taxe et exonération incompatibles")
    elif not isinstance(template, str) or not template.strip():
        raise ValueError("Modèle fiscal vérifié ou exonération explicite requis")
    for key in ("income_account", "cost_center"):
        if settings.get(key) is not None and not isinstance(settings[key], str):
            raise ValueError(f"Configuration {key} invalide")
    return {key: settings.get(key) for key in allowed}


def validate_inclusive_taxes(rows):
    """The listed catalog price is the final gross amount; never add a tax."""
    if not rows:
        raise ValueError("Modèle de taxes vide")
    for row in rows:
        if (row.get("charge_type") != "On Net Total"
                or int(row.get("included_in_print_rate") or 0) != 1
                or (row.get("add_deduct_tax") or "Add") != "Add"
                or not row.get("account_head")):
            raise ValueError("Taxes non inclusives ou trop complexes : revue comptable")
    return True
