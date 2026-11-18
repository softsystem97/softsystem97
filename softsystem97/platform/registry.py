"""Versioned, strict payload contracts for SS97's operational modules.

No business actions, remote control, payments, or AI are performed here.
The public-facing catalog must distinguish usable records from future engines.
"""

import json
import re
from datetime import datetime, timedelta


MODULES = {
    "V2": {"name": "Missions et techniciens", "fields": {
        "title": ("text", 120), "starts_at": ("datetime", None),
        "minutes": ("minutes", None), "instructions": ("text", 1500),
    }, "required": ("title", "starts_at", "minutes")},
    "V3": {"name": "Command Center", "fields": {
        "symptoms": ("text", 2000), "diagnostic": ("text", 2000),
        "risk": ("enum", ("low", "medium", "high")),
    }, "required": ("symptoms", "risk")},
    "V4": {"name": "SS97 ONE", "fields": {
        "coordination_note": ("text", 2000),
        "next_step": ("text", 500),
    }, "required": ("coordination_note",)},
    "V5": {"name": "SOS informatique", "fields": {
        "category": ("enum", ("network", "software", "hardware", "access", "other")),
        "urgency": ("enum", ("normal", "high", "critical")),
        "description": ("text", 2000),
    }, "required": ("category", "urgency", "description")},
    "V6": {"name": "Passeport informatique", "fields": {
        "asset_name": ("text", 120), "asset_type": ("enum", ("desktop", "laptop", "printer", "server", "network", "other")),
        "asset_tag": ("text", 120), "inventory_authorized": ("consent", None),
    }, "required": ("asset_name", "asset_type", "inventory_authorized")},
    "V7": {"name": "Maintenance proactive", "fields": {
        "asset_record": ("uuid", None), "interval_days": ("days", None),
        "next_due": ("date", None), "maintenance_note": ("text", 1500),
    }, "required": ("asset_record", "interval_days", "next_due")},
    "V8": {"name": "Réseau de techniciens", "fields": {
        "specialty": ("enum", ("systems", "networks", "security", "hardware", "software")),
        "escalation_reason": ("text", 1500), "territory": ("text", 120),
    }, "required": ("specialty", "escalation_reason")},
    "V9": {"name": "Cyber et résilience", "fields": {
        "finding": ("text", 2000), "severity": ("enum", ("low", "medium", "high", "critical")),
        "recommendation": ("text", 2000),
    }, "required": ("finding", "severity")},
    "V10": {"name": "Écosystème SS97", "fields": {
        "partner_name": ("text", 120), "offering": ("text", 1200),
        "verification_note": ("text", 1200),
    }, "required": ("partner_name", "offering")},
}

ALLOWED_STATES = {
    "SUBMITTED": frozenset(("IN_REVIEW", "CANCELLED")),
    "IN_REVIEW": frozenset(("COMPLETED", "CANCELLED")),
    "COMPLETED": frozenset(),
    "CANCELLED": frozenset(),
}


def catalog():
    """Return public schemas without advertising unimplemented engines."""
    return [
        {"version": version, "name": spec["name"],
         "fields": list(spec["fields"]), "required": list(spec["required"]),
         "capability": "secured_case_records"}
        for version, spec in MODULES.items()
    ]


def _valid_uuid(value):
    return isinstance(value, str) and re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", value
    ) is not None


def _datetime(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise ValueError("Date UTC attendue (YYYY-MM-DDTHH:MM:SSZ).")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Date invalide.") from None


def validate_payload(version, payload):
    """Reject unknown fields, excessive lengths, extra data and weak consent."""
    if not isinstance(version, str) or version not in MODULES or not isinstance(payload, dict):
        raise ValueError("Version ou données invalides.")
    spec = MODULES[version]
    if (not set(payload).issubset(spec["fields"]) or not set(spec["required"]).issubset(payload)):
        raise ValueError("Champs absents ou interdits.")
    checked = {}
    for field, value in payload.items():
        kind, limit = spec["fields"][field]
        if kind == "text":
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError("Texte invalide : " + field)
            value = value.strip()
        elif kind == "enum":
            if not isinstance(value, str) or value not in limit:
                raise ValueError("Choix invalide : " + field)
        elif kind in ("minutes", "days"):
            maximum = 180 if kind == "minutes" else 3650
            if type(value) is not int or not (1 <= value <= maximum):
                raise ValueError("Durée invalide : " + field)
        elif kind == "consent":
            if value is not True:
                raise ValueError("Autorisation explicite de l'inventaire requise.")
        elif kind == "uuid":
            if not _valid_uuid(value):
                raise ValueError("Identifiant invalide : " + field)
        elif kind == "datetime":
            _datetime(value)
        elif kind == "date":
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("Date invalide : " + field)
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                raise ValueError("Date invalide : " + field) from None
        checked[field] = value
    if len(json.dumps(checked, ensure_ascii=False)) > 9000:
        raise ValueError("Enregistrement trop volumineux.")
    return checked


def schedule_window(payload):
    """V2 scheduling interval; never infer time from an unverified browser clock."""
    checked = validate_payload("V2", payload)
    start = _datetime(checked["starts_at"])
    return start, start + timedelta(minutes=checked["minutes"])


def overlaps(first_start, first_end, second_start, second_end):
    return first_start < second_end and second_start < first_end


def can_change_state(current, target, audience, version):
    if not isinstance(current, str) or not isinstance(target, str):
        return False
    if target not in ALLOWED_STATES.get(current, ()):
        return False
    if audience == "technician":
        return True
    return audience == "client" and version == "V5" and target == "CANCELLED"
