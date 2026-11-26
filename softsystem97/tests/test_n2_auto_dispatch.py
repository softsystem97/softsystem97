import json
import frappe

from pathlib import Path

from softsystem97.tests.test_stripe_accounting import (
    TestStripeAccounting
)

from softsystem97.integrations.ticket_bridge import (
    auto_dispatch, policy, payment_gate
)


class TestN2AutoDispatch(TestStripeAccounting):

    def test_automatic_assignment(self):

        assert frappe.local.site == "audit.n2.localhost"

        accounts = json.loads(
            (Path.home() /
             "ss97-n2-comptes-lab.json").read_text()
        )

        tech = accounts["technicien"]["email"]
        other = accounts["technicien-b"]["email"]
        writer = accounts["service"]["email"]

        for user in (tech, other, writer):
            assert user.endswith("@example.invalid")

        old = frappe.conf.get("ss97_ticket_bridge")

        frappe.conf.ss97_ticket_bridge = {
            "enabled": True,
            "compatibility_confirmed": True,
            "technician_role": "SS97 Technician",
            "profile_required": False,
            "historical_integration": True,
            "enforce_paid_interventions": True,
            "email_enabled": False,
            "writer_user": writer,
            "business_authorizer":
                "softsystem97.integrations.ticket_bridge."
                "live_authorizer.authorize_ticket_operation"
        }

        try:

            frappe.set_user("Administrator")

            ticket = self.issue.name

            print("===== TICKET NON PAYE =====")

            result = auto_dispatch.dispatch_paid_ticket(
                ticket, [tech, other]
            )

            self.assertEqual(
                result["state"], "waiting_payment"
            )

            print("BLOCAGE AVANT PAIEMENT : OK")

            print("===== PAIEMENT STRIPE TEST =====")

            self.deliver(self.event())

            frappe.set_user("Administrator")

            self.assertTrue(
                payment_gate.issue_has_verified_stripe_payment(
                    ticket
                )
            )

            print("PAIEMENT VERIFIE : OK")

            print("===== SELECTION TECHNICIEN =====")

            eligible = auto_dispatch.eligible_technicians(
                [tech, other, writer]
            )

            self.assertEqual(
                {row["user"] for row in eligible},
                {tech, other}
            )

            expected = eligible[0]["user"]

            print("SELECTION N2 : OK")

            print("===== AFFECTATION AUTOMATIQUE =====")

            result = auto_dispatch.dispatch_paid_ticket(
                ticket, [tech, other]
            )

            self.assertEqual(
                result["state"], "assigned"
            )

            selected = result["technician"]

            self.assertEqual(selected, expected)

            self.assertTrue(
                policy.assigned(ticket, selected)
            )

            self.assertEqual(
                frappe.db.get_value(
                    "Issue", ticket, "ss97_technician"
                ),
                selected
            )

            print("AFFECTATION AUTOMATIQUE : OK")

            print("===== PROTECTION DOUBLONS =====")

            count_before = frappe.db.count(
                "ToDo",
                {
                    "reference_type": "Issue",
                    "reference_name": ticket,
                    "status": "Open"
                }
            )

            for _ in range(5):

                repeat = auto_dispatch.dispatch_paid_ticket(
                    ticket, [tech, other]
                )

                self.assertEqual(
                    repeat["state"], "already_assigned"
                )

                self.assertEqual(
                    repeat["technician"], selected
                )

            count_after = frappe.db.count(
                "ToDo",
                {
                    "reference_type": "Issue",
                    "reference_name": ticket,
                    "status": "Open"
                }
            )

            self.assertEqual(count_before, 1)
            self.assertEqual(count_after, 1)

            print("AUCUN DOUBLON : OK")

            print("===== SECURITE TECHNICIEN =====")

            frappe.set_user(selected)

            with self.assertRaises(frappe.PermissionError):

                auto_dispatch.dispatch_paid_ticket(
                    ticket, [tech, other]
                )

            print("AFFECTATION NON AUTORISEE BLOQUEE : OK")

            print("===================================")
            print("AFFECTATION AUTOMATIQUE N2 VALIDEE")
            print("===================================")

        finally:

            frappe.set_user("Administrator")
            frappe.db.rollback()
            frappe.conf.ss97_ticket_bridge = old
