"""Check role-only access cannot be used as a Cyber N4 qualification."""
import unittest
from softsystem97.integrations.ticket_bridge.bridge_profile_gate import (
    N4_ROLE, qualified_n4, profile_flag_valid,
)

class N4BridgeQualificationTests(unittest.TestCase):
    def test_n4_requires_profile_flag(self):
        self.assertTrue(profile_flag_valid(N4_ROLE, True))
        self.assertFalse(profile_flag_valid(N4_ROLE, False))
        self.assertFalse(profile_flag_valid(N4_ROLE, None))

    def test_other_legacy_tech_requires_explicit_false(self):
        self.assertTrue(profile_flag_valid("SS97 Technicien N3", False))
        self.assertFalse(profile_flag_valid("SS97 Technicien N3", True))

    def test_n4_qualification(self):
        valid = {"track": "CYBER", "state": "ACTIVE", "engagement": "FREELANCE"}
        self.assertTrue(qualified_n4(valid, [N4_ROLE]))
        self.assertFalse(qualified_n4(valid, [N4_ROLE, "SS97 Technicien N2"]))
        self.assertFalse(qualified_n4(None, [N4_ROLE]))
        for key, value in (("track","BANK"),("state","APPLIED"),("state","SUSPENDED"),("engagement","EMPLOYEE")):
            broken={**valid,key:value}
            self.assertFalse(qualified_n4(broken,[N4_ROLE]))
        self.assertFalse(qualified_n4(valid,["Customer"]))

    def test_bridge_authorization_calls_profile(self):
        from pathlib import Path
        src=(Path(__file__).resolve().parents[1]/"softsystem97/integrations/ticket_bridge/policy.py").read_text()
        self.assertIn("bridge_profile_gate.qualified_n4(profile, roles)",src)
        self.assertIn("bridge_profile_gate.profile_flag_valid(role,",src)
        self.assertIn("'SS97 Technician Profile', {'candidate_user': user}",src)
        self.assertNotIn("ignore_permissions=True",src)

if __name__ == "__main__":
    unittest.main()
