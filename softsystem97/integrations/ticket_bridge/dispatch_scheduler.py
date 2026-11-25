"""Traitement automatique des tickets payes.

Aucune operation comptable.
Aucune activation automatique des paiements LIVE.
Aucun endpoint HTTP public.
"""

import hashlib
import frappe

from . import policy, payment_gate, auto_dispatch


def configuration():

    bridge = frappe.conf.get("ss97_ticket_bridge") or {}

    if bridge.get("auto_dispatch_enabled") is not True:
        return {}

    routes = bridge.get("auto_dispatch_routes")

    if not isinstance(routes, dict):
        frappe.throw("Configuration affectation invalide.")

    if len(routes) > 100:
        frappe.throw("Limite de traitement depassee.")

    for ticket, candidates in routes.items():

        if not isinstance(ticket, str) or not ticket:
            frappe.throw("Ticket invalide.")

        if not isinstance(candidates, list):
            frappe.throw("Liste de techniciens invalide.")

        if len(candidates) > 100:
            frappe.throw("Trop de techniciens.")

        if any(
            not isinstance(user, str) or not user
            for user in candidates
        ):
            frappe.throw("Identifiant technicien invalide.")

    return routes


def process_ticket(issue_name):

    routes = configuration()

    if issue_name not in routes:
        return {"state": "not_configured"}

    policy.dispatcher()

    return auto_dispatch.dispatch_paid_ticket(
        issue_name,
        routes[issue_name]
    )


def run_pending():

    routes = configuration()

    if not routes:
        return {"state": "disabled", "requested": 0}

    policy.dispatcher()

    requested = 0

    for ticket in sorted(routes):

        issue = frappe.db.get_value(
            "Issue",
            ticket,
            ["status", "ss97_technician"],
            as_dict=True
        )

        if not issue:
            continue

        if issue.status != "Open":
            continue

        if issue.ss97_technician:
            continue

        if not payment_gate.issue_has_verified_stripe_payment(
            ticket
        ):
            continue

        job_id = "ss97-n2-" + hashlib.sha256(
            ticket.encode()
        ).hexdigest()

        frappe.enqueue(
            "softsystem97.integrations.ticket_bridge."
            "dispatch_scheduler.process_ticket",
            queue="default",
            timeout=120,
            job_id=job_id,
            deduplicate=True,
            issue_name=ticket
        )

        requested += 1

    return {
        "state": "processed",
        "requested": requested
    }
