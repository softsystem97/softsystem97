"""Read-only proof of client funds before any freelance settlement review.

This module never invokes a payout or trusts a browser-supplied payment flag.
It intentionally uses the existing Stripe-to-ERPNext posted-invoice verifier.
"""

import frappe

from .rules import fee_eur


def ticket_payment_evidence(mission):
    """Return a conservative state, including for free/unbilled tickets.

    NO_INVOICE permits *internal* review, not an automated transfer.
    A linked invoice must be unambiguous, customer-matched and fully paid.
    """
    try:
        if not frappe.get_meta("Sales Invoice").has_field("ss97_linked_issue"):
            return "UNAVAILABLE"
        invoices = frappe.get_all(
            "Sales Invoice", filters={"ss97_linked_issue": mission.ticket_name},
            fields=["name", "customer"], limit_page_length=2,
        )
        if not invoices:
            return "NO_INVOICE"
        if (len(invoices) != 1 or invoices[0].customer != mission.customer):
            return "UNVERIFIED"
        from softsystem97.integrations.ticket_bridge.payment_gate import issue_has_verified_stripe_payment
        return ("VERIFIED_PAID" if issue_has_verified_stripe_payment(mission.ticket_name) is True
                else "UNVERIFIED")
    except Exception:
        # Missing metadata, permissions, configuration or refund evidence never
        # become positive proof of payment.
        return "UNAVAILABLE"


def internal_financial_review_allowed(evidence):
    """Only free/unbilled or unequivocally paid tickets reach human review."""
    return evidence in {"NO_INVOICE", "VERIFIED_PAID"}


def amounts_match_eur(left, right):
    """Compare amounts without rounding invalid or floating-point inputs."""
    try:
        return fee_eur(str(left)) == fee_eur(str(right))
    except ValueError:
        return False
