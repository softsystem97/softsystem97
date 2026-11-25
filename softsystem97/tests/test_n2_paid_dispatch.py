import frappe
import json
import unittest

from pathlib import Path

from softsystem97.tests.test_stripe_accounting import (
    TestStripeAccounting
)

from softsystem97.integrations.ticket_bridge import (
    api, policy, payment_gate
)


class TestN2PaidDispatch(TestStripeAccounting):

    def test_n2_complete_payment_assignment(self):

        assert frappe.local.site == "audit.n2.localhost"
        assert frappe.conf.allow_tests is True
        assert frappe.conf.ss97_stripe_test_site is True
        assert frappe.conf.mute_emails is True
        assert frappe.conf.PAYMENTS_LIVE_ENABLED == 0

        frappe.set_user("Administrator")

        credentials = json.loads(
            (Path.home() / "ss97-n2-comptes-lab.json").read_text()
        )

        tech = credentials["technicien"]["email"]
        other = credentials["technicien-b"]["email"]
        writer = credentials["service"]["email"]

        for user in (tech, other, writer):
            assert user.endswith("@example.invalid")
            assert frappe.db.exists("User", user)

        role = "SS97 Technician"

        assert role in frappe.get_roles(tech)
        assert role in frappe.get_roles(other)

        print("N2 - HABILITATION : OK")

        meta = frappe.get_meta("Issue")

        if not meta.has_field("ss97_technician"):
            frappe.get_doc({
                "doctype": "Custom Field",
                "dt": "Issue",
                "fieldname": "ss97_technician",
                "label": "Technicien SS97",
                "fieldtype": "Link",
                "options": "User"
            }).insert()

            frappe.clear_cache(doctype="Issue")
            frappe.db.commit()

        field = frappe.get_meta("Issue").get_field(
            "ss97_technician"
        )

        assert field.fieldtype == "Link"
        assert field.options == "User"

        print("N2 - CHAMP TECHNICIEN : OK")

        old_config = frappe.conf.get("ss97_ticket_bridge")

        frappe.conf.ss97_ticket_bridge = {
            "enabled": True,
            "compatibility_confirmed": True,
            "technician_role": role,
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

            policy.settings()

            print("N2 - INTEGRATION HISTORIQUE : OK")

            ticket = self.issue.name

            assert not payment_gate.issue_has_verified_stripe_payment(
                ticket
            )

            frappe.db.savepoint("n2_unpaid")

            with self.assertRaises(frappe.PermissionError):
                api.assign_ticket(
                    ticket,
                    tech,
                    "n2-unpaid-" + frappe.generate_hash(length=12)
                )

            frappe.db.rollback(save_point="n2_unpaid")

            assert not policy.assigned(ticket, tech)

            print("N2 - TICKET NON PAYE BLOQUE : OK")

            self.deliver(self.event())

            frappe.set_user("Administrator")

            assert payment_gate.issue_has_verified_stripe_payment(
                ticket
            )

            print("N2 - PAIEMENT DE TEST VALIDE : OK")

            api.assign_ticket(
                ticket,
                tech,
                "n2-paid-" + frappe.generate_hash(length=12)
            )

            assert policy.assigned(ticket, tech)

            assert frappe.db.get_value(
                "Issue", ticket, "ss97_technician"
            ) == tech

            print("N2 - AFFECTATION APRES PAIEMENT : OK")

            frappe.set_user(tech)

            current = api.get_ticket(ticket)["ticket"]

            api.add_intervention(
                ticket,
                "Diagnostic N2 apres paiement valide",
                "n2-comment-" + frappe.generate_hash(length=12)
            )

            api.update_status(
                ticket,
                "Replied",
                current["modified"],
                "n2-status-" + frappe.generate_hash(length=12)
            )

            print("N2 - INTERVENTION AUTORISEE : OK")

            notifications = api.get_notifications()["notifications"]

            assert any(
                n.reference_name == ticket
                for n in notifications
            )

            print("N2 - NOTIFICATION TECHNICIEN : OK")

            frappe.set_user(other)

            with self.assertRaises(frappe.PermissionError):
                api.get_ticket(ticket)

            print("N2 - ISOLATION TECHNICIENS : OK")

            frappe.set_user(self.client)

            assert api.get_ticket(
                ticket, "client"
            )["ticket"]["status"] == "Replied"

            print("N2 - SUIVI CLIENT : OK")

            print("================================")
            print("CIRCUIT N2 AVEC PAIEMENT VALIDE")
            print("================================")

        finally:
            frappe.set_user("Administrator")
            frappe.db.rollback()
            frappe.conf.ss97_ticket_bridge = old_config
