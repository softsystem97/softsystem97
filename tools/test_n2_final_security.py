import unittest

from softsystem97.integrations.ticket_bridge.n2_profile_access import qualified

from softsystem97.integrations.ticket_bridge.bridge_profile_gate import profile_flag_valid

from softsystem97.integrations.stripe.clearing_routing import select_account


class TestN2Security(unittest.TestCase):

    def setUp(self):

        self.role = "SS97 Technicien N2"

        self.profile = {
            "track": "L2",
            "state": "ACTIVE",
            "engagement": "FREELANCE"
        }

    def test_active_profile(self):

        self.assertTrue(
            qualified(self.profile, [self.role])
        )

    def test_suspended_profiles(self):

        for state in (
            "SUSPENDED",
            "REVOKED",
            "IN_REVIEW",
            "PENDING",
            ""
        ):

            self.assertFalse(
                qualified(
                    dict(self.profile, state=state),
                    [self.role]
                )
            )

    def test_wrong_track(self):

        for track in ("BANK", "CYBER", ""):

            self.assertFalse(
                qualified(
                    dict(self.profile, track=track),
                    [self.role]
                )
            )

    def test_wrong_engagement(self):

        self.assertFalse(
            qualified(
                dict(self.profile, engagement=""),
                [self.role]
            )
        )

    def test_missing_profile(self):

        self.assertFalse(
            qualified(None, [self.role])
        )

    def test_specialty_separation(self):

        for role in (
            "SS97 Technicien N3",
            "SS97 Technicien N4"
        ):

            self.assertFalse(
                qualified(self.profile, [role])
            )

            self.assertFalse(
                qualified(
                    self.profile,
                    [self.role, role]
                )
            )

    def test_profile_required(self):

        self.assertTrue(
            profile_flag_valid(self.role, True)
        )

        self.assertFalse(
            profile_flag_valid(self.role, False)
        )

        self.assertTrue(
            profile_flag_valid(
                "SS97 Technicien N4", True
            )
        )


class TestStripeRouting(unittest.TestCase):

    def setUp(self):

        self.mapping = {
            "test": {
                "SS97 Audit": {
                    "EUR": "TEST EUR",
                    "USD": "TEST USD"
                }
            },
            "live": {
                "SS97 Audit": {
                    "EUR": "LIVE EUR",
                    "USD": "LIVE USD"
                }
            }
        }

    def test_currency_routing(self):

        for mode in ("test", "live"):

            for currency in ("EUR", "USD"):

                self.assertEqual(
                    select_account(
                        self.mapping,
                        mode,
                        "SS97 Audit",
                        currency
                    ),
                    mode.upper() + " " + currency
                )

    def test_unknown_company(self):

        with self.assertRaises(ValueError):

            select_account(
                self.mapping,
                "live",
                "UNKNOWN",
                "EUR"
            )

    def test_unknown_currency(self):

        with self.assertRaises(ValueError):

            select_account(
                self.mapping,
                "live",
                "SS97 Audit",
                "GBP"
            )

    def test_unknown_mode(self):

        with self.assertRaises(ValueError):

            select_account(
                self.mapping,
                "invalid",
                "SS97 Audit",
                "EUR"
            )

    def test_no_cross_mode_fallback(self):

        mapping = {
            "test": {
                "SS97 Audit": {
                    "USD": "TEST USD"
                }
            }
        }

        with self.assertRaises(ValueError):

            select_account(
                mapping,
                "live",
                "SS97 Audit",
                "USD",
                "TEST USD"
            )


if __name__ == "__main__":
    unittest.main()
