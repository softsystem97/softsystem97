"""Validation of structured N3 assistance records without Frappe or I/O."""

import re


REFERENCE_FIELDS = (
    "agency_ref", "asset_ref", "fallback_ref", "incident_ref",
    "equipment_model", "installed_version", "candidate_version",
)
REFERENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._/-]{0,79}")
CHOICES = {
    "service": ("WORKSTATION", "SCAN", "PRINT", "NETWORK", "AUTH", "TERMINAL", "OTHER"),
    "service_state": ("UNASSESSED", "INTERRUPTED", "WORKAROUND", "RESTORED"),
    "opening_check": ("NOT_CHECKED", "READY", "BLOCKED"),
    "escalation_team": ("NONE", "BRANCH", "NETWORK", "SECURITY", "MAINTAINER"),
    "onsite_status": ("NOT_NEEDED", "EQUIPMENT_REQUESTED", "VISIT_REQUESTED", "COMPLETE"),
    "rehearsal_result": ("NOT_TESTED", "PASS", "FAIL"),
    "rollback_result": ("NOT_TESTED", "PASS", "FAIL"),
    "pilot_result": ("NOT_TESTED", "PASS", "FAIL"),
}
TEST_RESULTS = ("rehearsal_result", "rollback_result", "pilot_result")
TEST_SCOPE = ("agency_ref", "asset_ref", "equipment_model", "installed_version", "candidate_version")


def parse_operation(payload):
    if not isinstance(payload, dict) or set(payload) != set(REFERENCE_FIELDS) | set(CHOICES):
        raise ValueError("Les champs du suivi Banque N3 sont incomplets ou inconnus.")

    operation = {}
    for field in REFERENCE_FIELDS:
        value = payload[field]
        if not isinstance(value, str) or len(value) > 80:
            raise ValueError("Une référence technique est invalide.")
        value = value.strip()
        if value and (not REFERENCE.fullmatch(value) or value.replace(" ", "").isdigit()):
            raise ValueError("Utilisez uniquement des références techniques sans données client.")
        operation[field] = value

    for field, choices in CHOICES.items():
        value = payload[field]
        if not isinstance(value, str) or value not in choices:
            raise ValueError("Un des statuts du suivi n’est pas reconnu.")
        operation[field] = value

    if not operation["agency_ref"] or not operation["asset_ref"]:
        raise ValueError("Les références de l’agence et du poste sont obligatoires.")
    if operation["service_state"] == "WORKAROUND" and not operation["fallback_ref"]:
        raise ValueError("Indiquez la référence de la solution de secours approuvée.")
    if operation["pilot_result"] != "NOT_TESTED" and (
        operation["rehearsal_result"] != "PASS" or operation["rollback_result"] != "PASS"
    ):
        raise ValueError("Vérifiez la correction et le retour arrière avant de renseigner le pilote.")
    if any(operation[key] != "NOT_TESTED" for key in TEST_RESULTS) and not all(
               operation[key] for key in ("equipment_model", "installed_version", "candidate_version")
           ):
        raise ValueError("Renseignez le modèle, la version en place et la version testée.")
    return operation


def validate_operation_update(previous, operation):
    if operation["service_state"] == "UNASSESSED" and previous["service_state"] != "UNASSESSED":
        raise ValueError("Un suivi commencé ne peut pas revenir à l’état non évalué.")
    if (any(previous[key] != "NOT_TESTED" for key in TEST_RESULTS)
            and any(previous[key] != operation[key] for key in TEST_SCOPE)
            and any(operation[key] != "NOT_TESTED" for key in TEST_RESULTS)):
        raise ValueError("Remettez les tests à « Non testé » lorsque le poste ou la version change.")


def continuity_times(previous, next_state, now):
    """Record attestations for the current interruption without inventing prior times."""
    previous_state = previous.get("service_state")
    times = {key: previous.get(key) for key in (
        "interrupted_at", "resumed_at", "restored_at",
    )}
    if next_state == "INTERRUPTED" and previous_state != "INTERRUPTED":
        return {"interrupted_at": now, "resumed_at": None, "restored_at": None}
    if next_state == "WORKAROUND" and previous_state != "WORKAROUND":
        times["resumed_at"] = times["resumed_at"] or now
        times["restored_at"] = None
    if next_state == "RESTORED" and previous_state != "RESTORED":
        times["resumed_at"] = times["resumed_at"] or now
        times["restored_at"] = now
    return times
