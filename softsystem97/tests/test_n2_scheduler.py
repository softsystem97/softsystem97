import json
import frappe

from pathlib import Path
from unittest.mock import patch

from softsystem97.tests import (
    test_stripe_accounting as fixtures
)

from softsystem97.integrations.ticket_bridge import (
    dispatch_scheduler,
    policy,
    payment_gate
)


class TestN2Scheduler(fixtures.TestStripeAccounting):

    def test_payment_to_automatic_dispatch(self):

        assert frappe.local.site == "audit.n2.localhost"
        assert frappe.conf.ss97_stripe_test_site is True

        accounts = json.loads(
            (Path.home() /
             "ss97-n2-comptes-lab.json").read_text()
        )

        tech = accounts["technicien"]["email"]
        other = accounts["technicien-b"]["email"]
        writer = accounts["service"]["email"]

        for user in (tech, other, writer):
            assert user.endswith("@example.invalid")

        ticket = self.issue.name

        old = frappe.conf.get("ss97_ticket_bridge")

        config = {
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
                "live_authorizer.authorize_ticket_operation",
            "auto_dispatch_enabled": False,
            "auto_dispatch_routes": {
                ticket: [tech, other]
            }
        }

        frappe.conf.ss97_ticket_bridge = config

        try:

            frappe.set_user("Administrator")

            print("===== AUTOMATISATION DESACTIVEE =====")

            with patch.object(frappe, "enqueue") as enqueue:

                result = dispatch_scheduler.run_pending()

                self.assertEqual(result["requested"], 0)

                enqueue.assert_not_called()

            print("DESACTIVATION SECURISEE : OK")

            config["auto_dispatch_enabled"] = True

            print("===== AVANT PAIEMENT =====")

            with patch.object(frappe, "enqueue") as enqueue:

                result = dispatch_scheduler.run_pending()

                self.assertEqual(result["requested"], 0)

                enqueue.assert_not_called()

            print("AUCUNE AFFECTATION AVANT PAIEMENT : OK")

            print("===== WEBHOOK STRIPE =====")

            frappe.set_user("Guest")

            response = self.deliver(self.event())

            self.assertTrue(response["ok"])

            frappe.set_user("Administrator")

            self.assertTrue(
                payment_gate.issue_has_verified_stripe_payment(
                    ticket
                )
            )

            print("PAIEMENT SIGNE ET COMPTABILISE : OK")

            print("===== FILE ATTENTE FRAPPE =====")

            with patch.object(frappe, "enqueue") as enqueue:

                result = dispatch_scheduler.run_pending()

                self.assertEqual(result["requested"], 1)

                enqueue.assert_called_once()

                arguments = enqueue.call_args.kwargs

                self.assertTrue(arguments["deduplicate"])
                self.assertEqual(
                    arguments["issue_name"],
                    ticket
                )

            print("PLANIFICATION AFFECTATION : OK")

            print("===== EXECUTION DU TRAITEMENT =====")

            result = dispatch_scheduler.process_ticket(
                ticket
            )

            self.assertEqual(result["state"], "assigned")

            selected = result["technician"]

            self.assertIn(selected, [tech, other])

            self.assertTrue(
                policy.assigned(ticket, selected)
            )

            print("TECHNICIEN AUTOMATIQUEMENT AFFECTE : OK")

            print("===== CONTROLE DOUBLONS =====")

            with patch.object(frappe, "enqueue") as enqueue:

                result = dispatch_scheduler.run_pending()

                self.assertEqual(result["requested"], 0)

                enqueue.assert_not_called()

            result = dispatch_scheduler.process_ticket(
                ticket
            )

            self.assertEqual(
                result["state"],
                "already_assigned"
            )

            count = frappe.db.count("ToDo", {
                "reference_type": "Issue",
                "reference_name": ticket,
                "status": "Open"
            })

            self.assertEqual(count, 1)

            print("AUCUN DOUBLON : OK")

            print("===== CONTROLE AUTORISATIONS =====")

            frappe.set_user(selected)

            with self.assertRaises(frappe.PermissionError):

                dispatch_scheduler.process_ticket(ticket)

            print("EXECUTION TECHNICIEN INTERDITE : OK")

            frappe.set_user("Administrator")

            config["auto_dispatch_routes"] = {}

            result = dispatch_scheduler.process_ticket(
                ticket
            )

            self.assertEqual(
                result["state"],
                "not_configured"
            )

            print("REVOCATION ROUTE : OK")

            print("===================================")
            print("CIRCUIT AUTOMATIQUE N2 : VALIDE")
            print("===================================")

        finally:

            frappe.set_user("Administrator")
            frappe.db.rollback()
            frappe.conf.ss97_ticket_bridge = old
