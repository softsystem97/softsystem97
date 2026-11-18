"""Offline safety tests: these do not connect to MeshCentral or Frappe."""

import unittest
from uuid import uuid4

from softsystem97.remote.gateway_protocol import (
    sign_gateway_event,
    verify_gateway_event,
)
from softsystem97.remote.receipts import (
    can_confirm_remote_activation,
    can_confirm_remote_disconnection,
)


class RemoteReceiptTests(unittest.TestCase):
    secret = "offline-mesh-gateway-test-secret-123456789"
    now = 1_795_000_000
    device = "server-bound-device-001"

    def setUp(self):
        self.session = str(uuid4())
        self.seen = set()

    def verified(self, event_type, second=0, session=None, device=None):
        raw = {
            "event_id": str(uuid4()),
            "session_id": session or self.session,
            "device_binding": device or self.device,
            "event_type": event_type,
            "issued_at": self.now + second,
        }
        signature = sign_gateway_event(raw, self.secret)

        def reserve_once(event_id, ttl_seconds):
            if event_id in self.seen:
                return False
            self.seen.add(event_id)
            return True

        return verify_gateway_event(raw, signature, self.secret,
                                    self.now + 20, reserve_once)

    def test_matching_consent_and_connection_allow_activation(self):
        consent = self.verified("LOCAL_CONSENT_GRANTED")
        connected = self.verified("DESKTOP_CONNECTED", 10)
        self.assertTrue(can_confirm_remote_activation(
            self.session, "CLIENT_APPROVED", self.device, consent, connected))

    def test_portal_click_alone_cannot_activate(self):
        self.assertFalse(can_confirm_remote_activation(
            self.session, "CLIENT_APPROVED", self.device, None, None))

    def test_unapproved_or_wrong_device_cannot_activate(self):
        consent = self.verified("LOCAL_CONSENT_GRANTED")
        connected = self.verified("DESKTOP_CONNECTED", 10)
        self.assertFalse(can_confirm_remote_activation(
            self.session, "CLIENT_READY", self.device, consent, connected))
        self.assertFalse(can_confirm_remote_activation(
            self.session, "CLIENT_APPROVED", "other-company-device", consent, connected))

    def test_valid_stop_receipt_matches_one_live_session(self):
        connected = self.verified("DESKTOP_CONNECTED")
        stopped = self.verified("DESKTOP_DISCONNECTED", 11)
        self.assertTrue(can_confirm_remote_disconnection(
            self.session, "ACTIVE", self.device, connected, stopped))
        self.assertTrue(can_confirm_remote_disconnection(
            self.session, "ERROR", self.device, connected, stopped))

    def test_stop_not_confirmed_by_a_browser_button(self):
        connected = self.verified("DESKTOP_CONNECTED")
        self.assertFalse(can_confirm_remote_disconnection(
            self.session, "ACTIVE", self.device, connected, None))

    def test_stop_rejects_wrong_binding_and_session(self):
        connected = self.verified("DESKTOP_CONNECTED")
        stopped = self.verified("DESKTOP_DISCONNECTED", 10,
                                device="other-company-device")
        self.assertFalse(can_confirm_remote_disconnection(
            self.session, "ACTIVE", self.device, connected, stopped))
        stopped_other = self.verified("DESKTOP_DISCONNECTED", 10,
                                      session=str(uuid4()))
        self.assertFalse(can_confirm_remote_disconnection(
            self.session, "ACTIVE", self.device, connected, stopped_other))

    def test_stop_rejects_wrong_order_or_state(self):
        connected = self.verified("DESKTOP_CONNECTED", 10)
        earlier = self.verified("DESKTOP_DISCONNECTED", 0)
        self.assertFalse(can_confirm_remote_disconnection(
            self.session, "ACTIVE", self.device, connected, earlier))
        later = self.verified("DESKTOP_DISCONNECTED", 15)
        self.assertFalse(can_confirm_remote_disconnection(
            self.session, "CLIENT_APPROVED", self.device, connected, later))

    def test_stop_rejects_non_disconnect_event(self):
        connected = self.verified("DESKTOP_CONNECTED")
        not_stopped = self.verified("LOCAL_CONSENT_GRANTED", 10)
        self.assertFalse(can_confirm_remote_disconnection(
            self.session, "ACTIVE", self.device, connected, not_stopped))


if __name__ == "__main__":
    unittest.main()
