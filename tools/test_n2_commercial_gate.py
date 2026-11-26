import unittest

from softsystem97.integrations.ticket_bridge.cockpit_commercial import (
    commercial_allowed,
    managed_ticket,
    PRODUCTION_SITE,
    AUTHORIZER,
)


class TestCommercialGate(unittest.TestCase):

    def setUp(self):

        self.cfg = {
            "enabled": True,
            "compatibility_confirmed": True,
            "cockpit_commercial_enabled": True,
            "profile_required": True,
            "historical_integration": True,
            "enforce_paid_interventions": True,
            "issue_scripts_reviewed": True,
            "technician_role": "SS97 Technicien N2",
            "business_authorizer": AUTHORIZER,
            "writer_user": "service@example.invalid",
        }

    def test_valid_configuration(self):

        self.assertTrue(
            commercial_allowed(
                PRODUCTION_SITE, {}, self.cfg
            )
        )

    def test_required_flags(self):

        for key in self.cfg:

            config = dict(self.cfg)
            config.pop(key)

            self.assertFalse(
                commercial_allowed(
                    PRODUCTION_SITE, {}, config
                )
            )

    def test_reject_test_environment(self):

        for key in (
            "allow_tests",
            "ss97_stripe_test_site",
            "ignore_csrf",
        ):

            self.assertFalse(
                commercial_allowed(
                    PRODUCTION_SITE,
                    {key: True},
                    self.cfg
                )
            )

    def test_reject_other_sites(self):

        self.assertFalse(
            commercial_allowed(
                "audit.n2.localhost", {}, self.cfg
            )
        )

    def test_reject_administrator_writer(self):

        config = dict(
            self.cfg,
            writer_user="Administrator"
        )

        self.assertFalse(
            commercial_allowed(
                PRODUCTION_SITE, {}, config
            )
        )

    def test_reject_other_specialties(self):

        for role in (
            "SS97 Technicien N3",
            "SS97 Technicien N4"
        ):

            config = dict(
                self.cfg, technician_role=role
            )

            self.assertFalse(
                commercial_allowed(
                    PRODUCTION_SITE, {}, config
                )
            )

    def test_remote_integration_pending(self):

        self.assertFalse(
            commercial_allowed(
                PRODUCTION_SITE,
                {"ss97_remote_assist": {"enabled": True}},
                self.cfg
            )
        )

    def test_guard_existing_intervention(self):

        self.assertTrue(
            managed_ticket(
                PRODUCTION_SITE,
                {},
                {"ss97_timer_status": "running"},
                {}
            )
        )

    def test_guard_n2_ticket(self):

        self.assertTrue(
            managed_ticket(
                PRODUCTION_SITE, self.cfg, {}, {}
            )
        )

    def test_unrelated_ticket(self):

        self.assertFalse(
            managed_ticket(
                PRODUCTION_SITE, {}, {}, {}
            )
        )


if __name__ == "__main__":
    unittest.main()
