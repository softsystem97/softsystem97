"""Pure security contract for a *future* isolated MeshCentral gateway.

This module neither contacts MeshCentral nor opens remote desktop access.
Only a trusted backend may use signed events; browser input must not be passed
to `verify_gateway_event` as if it came from the gateway.
"""

from dataclasses import dataclass
import hashlib
import hmac
import json
import re
from uuid import UUID


ALLOWED_EVENT_TYPES = frozenset({
    "LOCAL_CONSENT_GRANTED",
    "DESKTOP_CONNECTED",
    "DESKTOP_DISCONNECTED",
})
EVENT_FIELDS = frozenset({
    "event_id", "session_id", "device_binding", "event_type", "issued_at",
})
MAX_EVENT_AGE_SECONDS = 120
MAX_FUTURE_SKEW_SECONDS = 30
MAX_CONSENT_TO_CONNECTION_SECONDS = 60


@dataclass(frozen=True)
class VerifiedGatewayEvent:
    event_id: str
    session_id: str
    device_binding: str
    event_type: str
    issued_at: int


def _validate(event):
    if not isinstance(event, dict) or set(event) != EVENT_FIELDS:
        raise ValueError("Champs d'événement invalides.")
    for field in ("event_id", "session_id"):
        try:
            if not isinstance(event[field], str) or str(UUID(event[field], version=4)) != event[field]:
                raise ValueError
        except (ValueError, AttributeError, TypeError):
            raise ValueError("Identifiant d'événement invalide.") from None
    if (not isinstance(event["device_binding"], str)
            or not re.fullmatch(r"[A-Za-z0-9:_-]{8,128}", event["device_binding"])):
        raise ValueError("Liaison d'appareil invalide.")
    if event["event_type"] not in ALLOWED_EVENT_TYPES:
        raise ValueError("Type d'événement interdit.")
    if type(event["issued_at"]) is not int or event["issued_at"] < 0:
        raise ValueError("Horodatage invalide.")
    return VerifiedGatewayEvent(**event)


def _canonical(event):
    return json.dumps(event, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def _secret_bytes(secret):
    if not isinstance(secret, str) or len(secret.encode("utf-8")) < 32:
        raise ValueError("Secret passerelle trop faible.")
    return secret.encode("utf-8")


def sign_gateway_event(event, secret):
    """Lab helper; only the separate trusted gateway should sign in production."""
    _validate(event)
    return hmac.new(_secret_bytes(secret), _canonical(event), hashlib.sha256).hexdigest()


def verify_gateway_event(event, signature, secret, now_epoch, reserve_event_id):
    """Verify a trusted-gateway message and atomically reject replay.

    `reserve_event_id(id, ttl_seconds)` MUST be an atomic set-if-absent in the
    central store (Redis SET NX EX, or equivalent), returning True only once.
    Never use a process-local set in production and never accept missing guard.
    """
    checked = _validate(event)
    if type(now_epoch) is not int:
        raise ValueError("Heure serveur invalide.")
    age = now_epoch - checked.issued_at
    if age > MAX_EVENT_AGE_SECONDS or age < -MAX_FUTURE_SKEW_SECONDS:
        raise ValueError("Événement périmé ou daté dans le futur.")
    if not isinstance(signature, str) or re.fullmatch(r"[a-f0-9]{64}", signature) is None:
        raise ValueError("Signature invalide.")
    expected = sign_gateway_event(event, secret)
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Signature non authentique.")
    if not callable(reserve_event_id):
        raise ValueError("Protection anti-rejeu obligatoire.")
    if reserve_event_id(checked.event_id, MAX_EVENT_AGE_SECONDS + MAX_FUTURE_SKEW_SECONDS) is not True:
        raise ValueError("Événement déjà traité.")
    return checked


def can_activate_after_local_consent(session_id, current_state, consent, connected):
    """Permit state ACTIVE only after two verified, matching gateway events.

    The caller must ALSO re-check ticket ownership, assignment, active window
    and the authorised server-side device binding before state transition.
    """
    if (current_state != "CLIENT_APPROVED"
            or not isinstance(consent, VerifiedGatewayEvent)
            or not isinstance(connected, VerifiedGatewayEvent)):
        return False
    return (
        consent.event_type == "LOCAL_CONSENT_GRANTED"
        and connected.event_type == "DESKTOP_CONNECTED"
        and consent.event_id != connected.event_id
        and consent.session_id == connected.session_id == session_id
        and consent.device_binding == connected.device_binding
        and 0 <= connected.issued_at - consent.issued_at <= MAX_CONSENT_TO_CONNECTION_SECONDS
    )
