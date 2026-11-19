"""Server-side, explicitly published indicative EUR prices (never a charge)."""

from decimal import Decimal, InvalidOperation

TIERS_TO_FIELD = {
    "ESSENTIEL": "basique_eur", "SUPERIEUR": "premium_eur", "EXTREME": "ultra_eur",
}
SETTINGS = "SS97 Cyber Pricing"


def euro(value):
    """Accept decimal text, no float rounding, free offers, or hidden currency."""
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("Prix EUR invalide.")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Prix EUR invalide.") from exc
    if (not amount.is_finite() or amount <= 0 or amount > 100000
            or amount != amount.quantize(Decimal("0.01"))):
        raise ValueError("Prix EUR entre 0,01 et 100 000,00 avec deux décimales.")
    return format(amount, ".2f")


def snapshot(settings):
    """Fail closed on partial/unpublished administration and missing migration."""
    if not settings or not int(settings.get("is_published") or 0):
        return None
    try:
        return {tier: euro(settings.get(field)) for tier, field in TIERS_TO_FIELD.items()}
    except (ValueError, TypeError):
        return None
