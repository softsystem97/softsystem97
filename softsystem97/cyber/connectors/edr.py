"""Read-only EDR port. No provider registered, credentials, agent or remediation."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProtectionState:
    equipment_id: str
    protection: str  # Unknown / Protected / At risk, supplied by a verified provider.
    last_seen: str | None
    agent_version: str | None
    agent_state: str | None
    alert_references: tuple[str, ...] = ()
    proposed_actions: tuple[str, ...] = ()


class EDRAdapter(Protocol):
    def get_protection(self, verified_equipment_id: str) -> ProtectionState: ...


def capabilities():
    return {"provider_connected": False, "automatic_remediation": False}
