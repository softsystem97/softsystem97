"""Circuit pilote de finalisation des interventions N2."""

import frappe

from html import escape
from contextlib import contextmanager
from frappe.utils import now_datetime, cint

from . import api, policy, historical, cockpit, payment_gate

DONE = "Intervention terminée"
PENDING = "Validation administrateur en attente"
CLOSED = "Clôturé"

TARGETS = {
    "complete": DONE,
    "submit_close": PENDING,
    "admin_close": CLOSED
}

FIELDS = {
    "ss97_diagnostic": ("Long Text", None, None),
    "ss97_intervention_report": ("Text Editor", None, None),
    "ss97_checklist_close_done": ("Check", None, "0"),
    "ss97_remote_session_active": ("Check", None, "0"),
    "ss97_actual_duration_min": ("Int", None, "0"),
    "ss97_resolved_on": ("Datetime", None, None),
    "ss97_closed_on": ("Datetime", None, None),
    "ss97_resolved_by": ("Link", "User", None)
}


def deny(message):

    frappe.throw(message, frappe.PermissionError)


def install_schema():

    if frappe.local.site != "audit.n2.localhost":
        deny("Migration pilote locale uniquement.")

    if frappe.conf.get("ss97_stripe_test_site") is not True:
        deny("Environnement de test obligatoire.")

    frappe.only_for("System Manager")

    for name, (kind, options, default) in FIELDS.items():

        field = frappe.get_meta("Issue").get_field(name)

        if field:

            if field.fieldtype != kind:
                frappe.throw("Champ incompatible : " + name)

            if options and field.options != options:
                frappe.throw("Options incompatibles : " + name)

            continue

        data = {
            "doctype": "Custom Field",
            "dt": "Issue",
            "fieldname": name,
            "label": name.removeprefix("ss97_").replace("_", " "),
            "fieldtype": kind,
            "insert_after": "ss97_technician",
            "read_only": 1,
            "no_copy": 1
        }

        if options is not None:
            data["options"] = options

        if default is not None:
            data["default"] = default

        frappe.get_doc(data).insert()

        frappe.clear_cache(doctype="Issue")

        print("CHAMP CREE :", name)

    meta = frappe.get_meta("Issue")

    statuses = set(
        meta.get_field("ss97_ticket_status")
        .options.splitlines()
    )

    assert set(TARGETS.values()).issubset(statuses)

    print("STRUCTURE RAPPORT ET CLOTURE : OK")


def authorized(request):

    if not cockpit.enabled():
        return False

    action = request.operation.removeprefix("cockpit.")

    if action not in TARGETS:
        return False

    if request.target_status != TARGETS[action]:
        return False

    if request.actor != frappe.session.user:
        return False

    doc = api._issue(request.issue, lock=True)

    if str(doc.modified) != request.revision:
        return False

    if not doc.customer or doc.customer != request.customer:
        return False

    if not all(doc.meta.has_field(f) for f in FIELDS):
        return False

    if doc.ss97_security_suspend != 0:
        return False

    if cint(doc.ss97_remote_session_active):
        return False

    remote = frappe.conf.get("ss97_remote_assist") or {}

    if remote.get("enabled") is True:
        return False

    if not payment_gate.issue_has_verified_stripe_payment(doc.name):
        return False

    technician = doc.ss97_technician

    if not technician or technician != request.technician:
        return False

    if action == "admin_close":

        policy.dispatcher()
        doc.check_permission("write")

        if request.actor == technician:
            return False

    else:

        policy.authorize(doc, "technician")

        if technician != request.actor:
            return False

    if action == "complete":

        return (
            doc.ss97_ticket_status in (
                cockpit.RUNNING,
                cockpit.PAUSED
            )
            and doc.status in ("Open", "On Hold")
            and bool(doc.ss97_intervention_started_on)
        )

    if action == "submit_close":

        return (
            doc.ss97_ticket_status == DONE
            and doc.status in ("Open", "On Hold")
            and doc.ss97_timer_status == "stopped"
            and bool(doc.ss97_diagnostic)
            and bool(doc.ss97_intervention_report)
            and cint(doc.ss97_checklist_close_done) == 1
        )

    if action == "admin_close":

        return (
            doc.ss97_ticket_status == PENDING
            and doc.status == "Resolved"
            and doc.ss97_timer_status == "stopped"
            and bool(doc.ss97_diagnostic)
            and bool(doc.ss97_intervention_report)
            and cint(doc.ss97_checklist_close_done) == 1
        )

    return False


@contextmanager
def controlled_write():

    old = frappe.flags.get("ss97_cockpit_write")

    frappe.flags.ss97_cockpit_write = True

    try:
        yield
    finally:
        frappe.flags.ss97_cockpit_write = old


def validate_pilot_issue(doc, method=None):

    if frappe.local.site != "audit.n2.localhost":
        return

    previous = doc.get_doc_before_save()

    if not previous:
        return

    if not (
        previous.get("ss97_intervention_started_on")
        or doc.get("ss97_intervention_started_on")
    ):
        return

    protected = set(cockpit.REQUIRED_FIELDS) | set(FIELDS) | {
        "status",
        "ss97_proof_log"
    }

    changed = any(
        doc.get(field) != previous.get(field)
        for field in protected
    )

    if changed and frappe.flags.get("ss97_cockpit_write") is not True:
        deny("Utiliser le circuit controle du cockpit N2.")


def execute(
    name,
    action,
    expected_modified,
    diagnostic=None,
    report=None,
    checklist=None
):

    if not cockpit.enabled():
        deny("Cockpit pilote desactive.")

    if action not in TARGETS:
        deny("Action interdite.")

    if action == "admin_close":
        policy.dispatcher()
    else:
        policy.technician()

    actor = frappe.session.user

    doc = api._issue(name, lock=True)

    if str(doc.modified) != expected_modified:
        frappe.throw(
            "Ticket modifie. Actualiser.",
            frappe.TimestampMismatchError
        )

    historical.require_authorization(
        "cockpit." + action,
        doc,
        technician=doc.ss97_technician or "",
        target_status=TARGETS[action]
    )

    now = now_datetime()

    old_status = doc.ss97_ticket_status

    if action == "complete":

        diagnostic = str(diagnostic or "").strip()
        report = str(report or "").strip()

        if not 10 <= len(diagnostic) <= 10000:
            frappe.throw("Diagnostic obligatoire.")

        if not 10 <= len(report) <= 10000:
            frappe.throw("Rapport obligatoire.")

        if checklist not in (True, 1, "1", "true"):
            frappe.throw("Checklist obligatoire.")

        doc.ss97_diagnostic = diagnostic
        doc.ss97_intervention_report = escape(report)
        doc.ss97_checklist_close_done = 1

        if doc.ss97_timer_status == "running":

            doc.ss97_work_seconds = (
                cint(doc.ss97_work_seconds)
                + cockpit.elapsed(
                    doc.ss97_timer_resumed_on, now
                )
            )

        elif doc.ss97_timer_status == "paused":

            doc.ss97_pause_seconds = (
                cint(doc.ss97_pause_seconds)
                + cockpit.elapsed(
                    doc.ss97_pause_started_on, now
                )
            )

        else:
            deny("Chronometre incoherent.")

        doc.ss97_actual_duration_min = (
            cint(doc.ss97_work_seconds) + 59
        ) // 60

        doc.ss97_timer_status = "stopped"
        doc.ss97_pause_started_on = None
        doc.ss97_resolved_on = now
        doc.ss97_resolved_by = actor
        pass  # SS97 N2: resolution deferred

    elif action == "submit_close":
        doc.status = "Resolved"
    elif action == "admin_close":

        doc.ss97_closed_on = now
        doc.status = "Closed"

    doc.ss97_ticket_status = TARGETS[action]
    doc.ss97_client_message = TARGETS[action]

    line = (
        f"{now} | {actor} | "
        f"{old_status} -> {TARGETS[action]}"
    )

    for field in (
        "ss97_action_log",
        "ss97_status_transition_log",
        "ss97_proof_log"
    ):

        doc.set(
            field,
            (doc.get(field) or "") + "\n" + line
        )

    with controlled_write():

        if action == "admin_close":
            doc.save()
        else:
            with policy.native_issue_writer():
                doc.save()

    api._notify(
        doc,
        [doc.ss97_technician, api._client_recipient(doc)],
        TARGETS[action]
    )

    return {
        "ticket": doc.name,
        "status": doc.ss97_ticket_status,
        "native_status": doc.status,
        "work_seconds": doc.ss97_work_seconds,
        "duration_min": doc.ss97_actual_duration_min,
        "modified": str(doc.modified)
    }
