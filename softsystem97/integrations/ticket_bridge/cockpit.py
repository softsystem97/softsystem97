"""Cockpit N2 natif - pilote local securise."""

import frappe

from frappe.utils import now_datetime, get_datetime

from . import api, policy, historical, payment_gate

RUNNING = "Intervention en cours"
PAUSED = "Intervention en pause"

TARGETS = {
    "start": RUNNING,
    "pause": PAUSED,
    "resume": RUNNING,
}

REQUIRED_FIELDS = (
    "ss97_ticket_status",
    "ss97_technician",
    "ss97_accepted_on",
    "ss97_checklist_pre_done",
    "ss97_security_suspend",
    "ss97_intervention_started_on",
    "ss97_timer_resumed_on",
    "ss97_pause_started_on",
    "ss97_work_seconds",
    "ss97_pause_seconds",
    "ss97_timer_status",
    "ss97_action_log",
    "ss97_status_transition_log",
    "ss97_client_message",
)


def enabled():

    config = frappe.conf.get("ss97_ticket_bridge") or {}

    return (
        frappe.local.site == "audit.n2.localhost"
        and frappe.conf.get("allow_tests") is True
        and frappe.conf.get("ss97_stripe_test_site") is True
        and frappe.conf.get("PAYMENTS_LIVE_ENABLED") == 0
        and config.get("cockpit_pilot_enabled") is True
        and config.get("enforce_paid_interventions") is True
        and historical.enabled()
    )


def deny(message):

    frappe.throw(message, frappe.PermissionError)


def authorized(request):

    if not enabled():
        return False

    action = request.operation.removeprefix("cockpit.")

    if action not in TARGETS:
        return False

    if request.target_status != TARGETS[action]:
        return False

    if request.actor != frappe.session.user:
        return False

    doc = api._issue(request.issue, lock=True)

    policy.authorize(doc, "technician")

    if not all(
        doc.meta.has_field(f)
        for f in REQUIRED_FIELDS
    ):
        return False

    if str(doc.modified) != request.revision:
        return False

    if doc.customer != request.customer:
        return False

    if doc.ss97_technician != request.actor:
        return False

    if request.technician != request.actor:
        return False

    if doc.status in ("Closed", "Resolved"):
        return False

    if doc.ss97_security_suspend != 0:
        return False

    if not payment_gate.issue_has_verified_stripe_payment(
        doc.name
    ):
        return False

    state = doc.ss97_ticket_status

    if action == "start":

        return (
            state in (
                "Accepté par le technicien",
                "Prêt à commencer"
            )
            and doc.status == "Open"
            and bool(doc.ss97_accepted_on)
            and bool(doc.ss97_checklist_pre_done)
            and not doc.ss97_intervention_started_on
        )

    if action == "pause":

        return (
            state == RUNNING
            and doc.status == "Open"
            and doc.ss97_timer_status == "running"
            and bool(doc.ss97_timer_resumed_on)
            and not doc.ss97_pause_started_on
        )

    if action == "resume":

        return (
            state == PAUSED
            and doc.status == "On Hold"
            and doc.ss97_timer_status == "paused"
            and bool(doc.ss97_pause_started_on)
            and bool(doc.ss97_checklist_pre_done)
        )

    return False


def elapsed(start, end):

    seconds = (
        get_datetime(end) - get_datetime(start)
    ).total_seconds()

    return max(0, int(seconds))


def execute(issue_name, action, expected_modified):

    if not enabled():
        deny("Cockpit pilote desactive.")

    if action not in TARGETS:
        deny("Action non autorisee.")

    actor = policy.technician()

    doc = api._issue(issue_name, lock=True)

    policy.authorize(doc, "technician")

    frappe.db.get_value(
        "User", actor, "name", for_update=True
    )

    if str(doc.modified) != expected_modified:
        frappe.throw(
            "Ticket modifie : rechargez.",
            frappe.TimestampMismatchError
        )

    historical.require_authorization(
        "cockpit." + action,
        doc,
        technician=actor,
        target_status=TARGETS[action]
    )

    if action in ("start", "resume"):

        other = frappe.db.get_value(
            "Issue",
            {
                "ss97_technician": actor,
                "ss97_timer_status": "running",
                "name": ["!=", doc.name],
            },
            "name",
            for_update=True
        )

        if other:
            deny("Autre intervention deja active.")

    now = now_datetime()

    previous = doc.ss97_ticket_status

    if action == "start":

        doc.ss97_intervention_started_on = now
        doc.ss97_timer_resumed_on = now
        doc.ss97_pause_started_on = None
        doc.ss97_work_seconds = 0
        doc.ss97_pause_seconds = 0
        doc.ss97_timer_status = "running"
        doc.status = "Open"

    elif action == "pause":

        doc.ss97_work_seconds = int(
            doc.ss97_work_seconds or 0
        ) + elapsed(
            doc.ss97_timer_resumed_on, now
        )

        doc.ss97_pause_started_on = now
        doc.ss97_timer_status = "paused"
        doc.status = "On Hold"

    elif action == "resume":

        doc.ss97_pause_seconds = int(
            doc.ss97_pause_seconds or 0
        ) + elapsed(
            doc.ss97_pause_started_on, now
        )

        doc.ss97_timer_resumed_on = now
        doc.ss97_pause_started_on = None
        doc.ss97_timer_status = "running"
        doc.status = "Open"

    doc.ss97_ticket_status = TARGETS[action]

    line = (
        f"{now} | {actor} | "
        f"{previous} -> {TARGETS[action]}"
    )

    for field in (
        "ss97_action_log",
        "ss97_status_transition_log"
    ):

        doc.set(
            field,
            (doc.get(field) or "") + "\n" + line
        )

    doc.ss97_client_message = TARGETS[action]

    from .cockpit_completion import controlled_write
    with controlled_write():
        with policy.native_issue_writer():
            doc.save()

    api._notify(
        doc,
        [actor, api._client_recipient(doc)],
        TARGETS[action]
    )

    return {
        "ticket": doc.name,
        "status": doc.ss97_ticket_status,
        "timer": doc.ss97_timer_status,
        "work_seconds": doc.ss97_work_seconds,
        "pause_seconds": doc.ss97_pause_seconds,
        "modified": str(doc.modified),
    }
