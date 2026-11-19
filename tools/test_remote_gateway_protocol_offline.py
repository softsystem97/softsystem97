"""Offline contract checks; no actual MeshCentral session is started."""

import unittest
from uuid import uuid4

from softsystem97.remote.gateway_protocol import (
    can_activate_after_local_consent, sign_gateway_event, verify_gateway_event,
)


class TestGatewayProtocol(unittest.TestCase):
    secret = "gateway-lab-secret-" * 4
    now = 1795000000

    def setUp(self):
        self.session_id = str(uuid4())
        self.seen = set()

    def event(self, kind="LOCAL_CONSENT_GRANTED", seconds=0, device="bound-device-01"):
        return {
            "event_id": str(uuid4()), "session_id": self.session_id,
            "device_binding": device, "event_type": kind,
            "issued_at": self.now + seconds,
        }

    def reserve(self, event_id, ttl):
        if event_id in self.seen:
            return False
        self.seen.add(event_id)
        return True

    def verify(self, event, signature=None):
        return verify_gateway_event(event, signature or sign_gateway_event(event, self.secret),
                                    self.secret, self.now + 30, self.reserve)

    def test_valid_signed_event_is_accepted_once(self):
        event = self.event()
        self.assertEqual(self.verify(event).event_type, "LOCAL_CONSENT_GRANTED")
        with self.assertRaisesRegex(ValueError, "déjà traité"):
            self.verify(event)

    def test_tampered_event_is_rejected(self):
        event = self.event()
        signature = sign_gateway_event(event, self.secret)
        event["device_binding"] = "bound-device-02"
        with self.assertRaisesRegex(ValueError, "non authentique"):
            self.verify(event, signature)

    def test_invalid_or_expired_events_fail_closed(self):
        for bad in (self.event(seconds=-200), self.event(seconds=100),
                    self.event(kind="UNATTENDED_ACCESS")):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.verify(bad)

    def test_replay_store_is_required(self):
        event = self.event()
        with self.assertRaisesRegex(ValueError, "anti-rejeu"):
            verify_gateway_event(event, sign_gateway_event(event, self.secret),
                                 self.secret, self.now, None)

    def test_weak_secret_rejected(self):
        with self.assertRaisesRegex(ValueError, "trop faible"):
            sign_gateway_event(self.event(), "small")

    def test_local_consent_precedes_activation(self):
        consent = self.verify(self.event())
        connected = self.verify(self.event("DESKTOP_CONNECTED", seconds=15))
        self.assertTrue(can_activate_after_local_consent(self.session_id, "CLIENT_APPROVED", consent, connected))
        self.assertFalse(can_activate_after_local_consent(self.session_id, "CREATED", consent, connected))
        self.assertFalse(can_activate_after_local_consent(str(uuid4()), "CLIENT_APPROVED", consent, connected))

    def test_cross_device_and_wrong_order_fail(self):
        consent = self.verify(self.event())
        wrong_device = self.verify(self.event("DESKTOP_CONNECTED", seconds=10,
                                              device="bound-device-02"))
        earlier = self.verify(self.event("DESKTOP_CONNECTED", seconds=-1))
        self.assertFalse(can_activate_after_local_consent(self.session_id,
                         "CLIENT_APPROVED", consent, wrong_device))
        self.assertFalse(can_activate_after_local_consent(self.session_id,
                         "CLIENT_APPROVED", consent, earlier))


if __name__ == "__main__":
    unittest.main()
