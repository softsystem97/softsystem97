"""Pure access and workflow rules for technician onboarding and missions."""

from decimal import Decimal, InvalidOperation


TRACKS = {
    "L2": {"label": "Informatique généraliste — N2", "role": "SS97 Technicien N2"},
    "BANK": {"label": "Informatique bancaire — N3", "role": "SS97 Technicien N3"},
    "CYBER": {"label": "Cybersécurité — N4", "role": "SS97 Technicien N4"},
}
TRACK_ROLES = frozenset(item["role"] for item in TRACKS.values())
SENSITIVE_TRACKS = frozenset({"BANK", "CYBER"})
PROFILE_TRANSITIONS = {
    "APPLIED": frozenset({"IN_REVIEW", "REJECTED"}),
    "IN_REVIEW": frozenset({"EXAM_VALIDATED", "REJECTED"}),
    "EXAM_VALIDATED": frozenset({"DOCUMENTS_VALIDATED", "REJECTED"}),
    "DOCUMENTS_VALIDATED": frozenset({"CONTRACT_SIGNED", "REJECTED"}),
    "CONTRACT_SIGNED": frozenset({"ACTIVE", "REJECTED"}),
    "ACTIVE": frozenset({"SUSPENDED"}),
    "SUSPENDED": frozenset({"ACTIVE", "REJECTED"}),
    "REJECTED": frozenset(),
}
MISSION_TRANSITIONS = {
    "PENDING_APPROVAL": frozenset({"OFFERED", "CANCELLED"}),
    "OFFERED": frozenset({"ACCEPTED", "DECLINED", "CANCELLED"}),
    "ACCEPTED": frozenset({"IN_PROGRESS", "CANCELLED"}),
    "IN_PROGRESS": frozenset({"REPORT_SUBMITTED", "CANCELLED"}),
    "REPORT_SUBMITTED": frozenset({"CLIENT_ACCEPTED", "DISPUTED"}),
    "REWORK_PENDING_APPROVAL": frozenset({"CANCELLED"}),
    "CLIENT_ACCEPTED": frozenset(),
    "DECLINED": frozenset(),
    "CANCELLED": frozenset(),
    "DISPUTED": frozenset({"CANCELLED"}),
}


def track_settings(track):
    if not isinstance(track, str) or track not in TRACKS:
        raise ValueError("Filière technicien inconnue.")
    return TRACKS[track]


def exact_track_role(roles, track):
    """An active worker must have their track role and no other track role."""
    expected = track_settings(track)["role"]
    assigned = set(roles) & TRACK_ROLES
    return assigned == {expected}


def next_profile_state(old, new):
    return isinstance(new, str) and new in PROFILE_TRANSITIONS.get(old, ())


def next_mission_state(old, new):
    return isinstance(new, str) and new in MISSION_TRANSITIONS.get(old, ())


def fee_eur(value):
    """Reject float inputs and exponents; staff-entered EUR estimate only."""
    if not isinstance(value, str) or not value or len(value) > 16:
        raise ValueError("Montant EUR invalide.")
    if not value.replace(".", "", 1).isdigit() or value.count(".") > 1:
        raise ValueError("Montant EUR invalide.")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Montant EUR invalide.") from exc
    if result <= 0 or result > Decimal("100000") or result.as_tuple().exponent < -2:
        raise ValueError("Montant EUR hors limites.")
    return f"{result:.2f}"


def reference(value, name="Référence"):
    if not isinstance(value, str) or not 5 <= len(value.strip()) <= 120:
        raise ValueError(f"{name} obligatoire (5 à 120 caractères).")
    if any(ord(char) < 32 for char in value):
        raise ValueError(f"{name} invalide.")
    return value.strip()


def short_note(value, maximum=2000):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
        raise ValueError("Texte obligatoire ou trop long.")
    return value.strip()
