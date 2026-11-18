"""Fail-closed checks for evidence returned by a future MeshCentral gateway.

These pure functions cannot access a desktop or change an SS97 ticket. Callers
must first verify each event's HMAC, age and replay ID with
``verify_gateway_event``. The expected device binding MUST be loaded from the
trusted SS97 server-side ticket/device association, never the browser.
"""

from .gateway_protocol import (
    VerifiedGatewayEvent,
    can_activate_after_local_consent,
)


def _bound(event, session_id, expected_device_binding):
    return (
        isinstance(event, VerifiedGatewayEvent)
        and isinstance(session_id, str)
        and bool(session_id)
        and isinstance(expected_device_binding, str)
        and bool(expected_device_binding)
        and event.session_id == session_id
        and event.device_binding == expected_device_binding
    )


def can_confirm_remote_activation(
    session_id, current_state, expected_device_binding, consent, connected
):
    """Require local consent, connected desktop and the server-bound device.

    The calling backend must additionally recheck ticket ownership, assigned
    technician, invitation window and a locally present consenting customer.
    No browser-provided connection status is acceptable evidence.
    """
    return (
        _bound(consent, session_id, expected_device_binding)
        and _bound(connected, session_id, expected_device_binding)
        and can_activate_after_local_consent(
            session_id, current_state, consent, connected
        )
    )


def can_confirm_remote_disconnection(
    session_id, current_state, expected_device_binding, connected, disconnected
):
    """Confirm that the matching desktop really disconnected.

    This can reconcile an ACTIVE or ERROR state; it does not itself terminate
    the remote session. The backend must obtain the events from an authenticated
    gateway and persist the confirmed transition before returning ENDED.
    """
    return (
        current_state in ("ACTIVE", "ERROR")
        and _bound(connected, session_id, expected_device_binding)
        and _bound(disconnected, session_id, expected_device_binding)
        and connected.event_type == "DESKTOP_CONNECTED"
        and disconnected.event_type == "DESKTOP_DISCONNECTED"
        and connected.event_id != disconnected.event_id
        and disconnected.issued_at >= connected.issued_at
    )
