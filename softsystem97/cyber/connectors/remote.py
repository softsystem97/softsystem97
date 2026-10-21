"""RustDesk/equivalent future port; deliberately incapable of opening a session."""

from typing import Protocol


class RemoteEngine(Protocol):
    def revoke(self, verified_session_reference: str) -> bool: ...


class DisconnectedRemoteEngine:
    def start(self, *args, **kwargs):
        raise RuntimeError("remote_engine_not_connected")

    def capabilities(self):
        return {"connected": False, "can_start": False, "agent_installed": False}
