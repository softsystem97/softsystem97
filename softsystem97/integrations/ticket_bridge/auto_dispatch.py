"""Affectation automatique SS97 apres paiement verifie."""

import hashlib
import frappe

from . import api, policy, historical, payment_gate


def eligible_technicians(candidates):

    config = policy.settings()
    role = config["technician_role"]

    lab = (
        frappe.local.site == "audit.n2.localhost"
        and frappe.conf.get("allow_tests") is True
        and frappe.conf.get("ss97_stripe_test_site") is True
        and frappe.conf.get("PAYMENTS_LIVE_ENABLED") == 0
    )

    if role != "SS97 Technicien N2":
        if not (lab and role == "SS97 Technician"):
            frappe.throw("Role N2 officiel requis.")

    if not isinstance(candidates, (list, tuple)):
        frappe.throw("Liste de techniciens requise.")

    eligible = []

    for user in sorted(set(candidates)):

        if user in ("Administrator", "Guest"):
            continue

        if not frappe.db.get_value(
            "User", user, "enabled"
        ):
            continue

        if role not in frappe.get_roles(user):
            continue

        try:
            policy.technician(user)
        except frappe.PermissionError:
            continue

        workload = frappe.db.count(
            "ToDo",
            {
                "allocated_to": user,
                "reference_type": "Issue",
                "status": "Open"
            }
        )

        eligible.append({
            "user": user,
            "workload": workload
        })

    return sorted(
        eligible,
        key=lambda item: (
            item["workload"],
            item["user"]
        )
    )


def dispatch_paid_ticket(issue_name, candidates):

    policy.dispatcher()

    config = policy.settings()

    if not historical.enabled():
        frappe.throw(
            "Integration historique requise.",
            frappe.PermissionError
        )

    if config.get("enforce_paid_interventions") is not True:
        frappe.throw(
            "Controle des paiements obligatoire.",
            frappe.PermissionError
        )

    issue = api._issue(issue_name, lock=True)

    issue.check_permission("write")

    if issue.status == "Closed":
        return {"state": "closed"}

    if not payment_gate.issue_has_verified_stripe_payment(
        issue.name
    ):
        return {"state": "waiting_payment"}

    current = issue.get("ss97_technician")

    if current:

        if policy.assigned(issue.name, current):
            return {
                "state": "already_assigned",
                "technician": current
            }

        return {"state": "manual_review"}

    if frappe.db.exists("ToDo", {
        "reference_type": "Issue",
        "reference_name": issue.name,
        "status": "Open"
    }):
        return {"state": "manual_review"}

    if issue.status != "Open":
        return {"state": "manual_review"}

    eligible = eligible_technicians(candidates)

    if not eligible:
        return {"state": "no_eligible_technician"}

    selected = eligible[0]["user"]

    request_id = "auto-n2-" + hashlib.sha256(
        f"{issue.name}:{selected}".encode()
    ).hexdigest()

    result = api.assign_ticket(
        issue.name,
        selected,
        request_id
    )

    if not policy.assigned(issue.name, selected):
        frappe.throw(
            "Affectation non confirmee.",
            frappe.PermissionError
        )

    return {
        "state": "assigned",
        "ticket": issue.name,
        "technician": selected,
        "previous_workload": eligible[0]["workload"],
        "result": result
    }
