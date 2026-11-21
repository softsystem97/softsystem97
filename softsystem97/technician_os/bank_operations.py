"""Mission-scoped N3 operation records. No remote access or deployment is granted here."""

import frappe
from frappe.utils import now_datetime

from . import api
from .bank_operation_rules import (
    CHOICES, REFERENCE_FIELDS, continuity_times, parse_operation, validate_operation_update,
)


DOCTYPE = "SS97 Bank Operation"
FIELDS = (*REFERENCE_FIELDS, *CHOICES)
TIMES = ("interrupted_at", "resumed_at", "restored_at")


def _scope(mission_id, write=False):
    api._enabled()
    profile = api._my_active_profile()
    if profile.track != "BANK":
        frappe.throw("Habilitation Banque N3 requise.", frappe.PermissionError)
    mission = api._mission_by_id(mission_id, lock=write)
    if mission.track != "BANK" or mission.technician != profile.candidate_user:
        frappe.throw("Mission bancaire inaccessible.", frappe.PermissionError)
    ticket = api._authorized_ticket(mission, "technician")
    if write and (mission.state != "IN_PROGRESS" or ticket.status == "Closed"):
        frappe.throw("Une mission bancaire en cours est requise.", frappe.PermissionError)
    if not frappe.db.table_exists(DOCTYPE):
        frappe.throw("La migration du suivi Banque N3 est requise.", frappe.PermissionError)
    return mission


def _record(mission_id, lock=False):
    name = frappe.db.get_value(DOCTYPE, {"mission": mission_id}, "name")
    return frappe.get_doc(DOCTYPE, name, for_update=lock) if name else None


def _view(record):
    if record is None:
        return {
            "revision": 0,
            "values": {**dict.fromkeys(REFERENCE_FIELDS, ""),
                       **{key: values[0] for key, values in CHOICES.items()}},
            **dict.fromkeys(TIMES),
        }
    return {
        "revision": int(record.revision),
        "values": {key: record.get(key) or "" for key in FIELDS},
        **{key: str(record.get(key)) if record.get(key) else None for key in TIMES},
    }


@frappe.whitelist(methods=["GET"])
def get_bank_operation(mission_id):
    mission = _scope(mission_id)
    return _view(_record(mission.name))


@frappe.whitelist(methods=["POST"])
def save_bank_operation(mission_id, revision, values):
    mission = _scope(mission_id, write=True)
    record = _record(mission.name, lock=True)
    current = _view(record)
    if type(revision) is not int or revision != current["revision"]:
        frappe.throw("Le suivi a changé. Rechargez la mission avant de poursuivre.")

    try:
        operation = parse_operation(values)
        validate_operation_update(current["values"], operation)
    except ValueError as error:
        frappe.throw(str(error))

    if record and current["values"] == operation:
        return current
    previous = record.as_dict() if record else {}
    times = continuity_times(previous, operation["service_state"], now_datetime())
    if not record:
        record = frappe.get_doc({"doctype": DOCTYPE, "mission": mission.name})
    record.update({**operation, **times, "revision": revision + 1})
    record.save(ignore_permissions=True)
    api._log("MISSION", mission.name, "BANK_OPERATION_" + operation["service_state"],
             mission.technician)
    return _view(record)
