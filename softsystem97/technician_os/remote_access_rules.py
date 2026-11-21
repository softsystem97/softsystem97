"""Fail-closed N2/N3 remote-support authorization policy.

Pure checks only: no remote desktop connection, secrets, credentials, database
reads or automatic role grants. Callers MUST build the evidence from fresh,
server-side records; client-supplied booleans are not authorization evidence.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .rules import exact_track_role

CONSENT_MAX_AGE = timedelta(minutes=15)
MAX_DURATION = {"L2": timedelta(minutes=60),
                "BANK": timedelta(minutes=30)}


class RemoteAccessDenied(ValueError):
    """Denied; the caller must not create a remote provider session."""


@dataclass(frozen=True)
class RemoteAccessEvidence:
    track: str
    ticket: str
    device: str
    technician: str
    customer: str
    profile_state: str
    technician_enabled: bool
    ticket_open: bool
    assigned_technician: str
    assignment_approved: bool
    technician_roles: tuple[str, ...]
    consenting_user: str
    consent_ticket: str
    consent_device: str
    consent_technician: str
    consent_at: datetime
    expires_at: datetime
    now: datetime
    consent_revoked: bool = False
    session_closed: bool = False
    mandate_reference: str = ""
    mandate_ticket: str = ""
    mandate_device: str = ""
    mandate_technician: str = ""
    manager_approvals: tuple[str, ...] = field(default_factory=tuple)


def _identity(value):
    return (isinstance(value, str) and 3 <= len(value.strip()) <= 140
            and value == value.strip()
            and not any(ord(char) < 32 for char in value))


def _aware(value):
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def authorize_remote_start(evidence: RemoteAccessEvidence):
    """Return minimum non-secret launch metadata, otherwise fail closed.

    A separate Frappe handler must verify the ticket, user, active specialty
    profile, assignment receipt, client consent and any manager approvals
    directly in trusted records *on every attempt*. A provider adapter must
    create short-lived sessions and revoke them on customer withdrawal.
    """
    if not isinstance(evidence, RemoteAccessEvidence) or evidence.track not in MAX_DURATION:
        raise RemoteAccessDenied("Filière distante non autorisée.")
    if not all(_identity(value) for value in (
        evidence.ticket, evidence.device, evidence.technician, evidence.customer,
    )) or evidence.customer == evidence.technician:
        raise RemoteAccessDenied("Identité ou périmètre de session invalide.")
    if (evidence.technician_enabled is not True
            or evidence.profile_state != "ACTIVE"
            or not isinstance(evidence.technician_roles, (tuple, list))
            or not exact_track_role(evidence.technician_roles, evidence.track)
            or evidence.ticket_open is not True
            or evidence.assignment_approved is not True
            or evidence.assigned_technician != evidence.technician):
        raise RemoteAccessDenied("Habilitation ou affectation indisponible.")
    if evidence.consent_revoked is not False or evidence.session_closed is not False:
        raise RemoteAccessDenied("Consentement ou session révoqué.")
    if (evidence.consenting_user != evidence.customer
            or evidence.consent_ticket != evidence.ticket
            or evidence.consent_device != evidence.device
            or evidence.consent_technician != evidence.technician):
        raise RemoteAccessDenied("Accord client absent ou hors périmètre.")
    if not all(_aware(value) for value in (
        evidence.now, evidence.consent_at, evidence.expires_at,
    )):
        raise RemoteAccessDenied("Horodatage serveur invalide.")
    consent_age = evidence.now - evidence.consent_at
    duration = evidence.expires_at - evidence.now
    if (consent_age < timedelta(0) or consent_age > CONSENT_MAX_AGE
            or duration <= timedelta(0) or duration > MAX_DURATION[evidence.track]):
        raise RemoteAccessDenied("Accord périmé ou durée excessive.")
    if evidence.track == "BANK":
        approvals = evidence.manager_approvals
        if (not _identity(evidence.mandate_reference)
                or evidence.mandate_ticket != evidence.ticket
                or evidence.mandate_device != evidence.device
                or evidence.mandate_technician != evidence.technician
                or not isinstance(approvals, (tuple, list))
                or len(approvals) != 2
                or not all(_identity(person) for person in approvals)
                or len(set(approvals)) != 2
                or any(person in {evidence.technician, evidence.customer}
                       for person in approvals)):
            raise RemoteAccessDenied("Mandat bancaire et double approbation requis.")
    return {
        "authorized": True,
        "track": evidence.track,
        "ticket": evidence.ticket,
        "device": evidence.device,
        "expires_at": evidence.expires_at.isoformat(),
    }
