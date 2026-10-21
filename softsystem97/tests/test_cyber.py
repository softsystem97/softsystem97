"""Real isolated Frappe document/API regressions; no external cyber provider."""

import unittest

import frappe

from softsystem97.cyber import api
from softsystem97.cyber import permissions as access


class TestCyber(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not frappe.conf.allow_tests or not frappe.local.site.startswith(
            ("audit.", "test_")
        ):
            raise RuntimeError("Disposable audit/test site required")
        frappe.set_user("Administrator")
        suffix = frappe.generate_hash(length=8)
        cls.users = []
        configs = [
            ("manager", ["SS97 Cyber Manager"]),
            ("director", ["SS97 Cyber Direction"]),
            ("tech", ["SS97 Cyber Technician"]),
            ("othertech", ["SS97 Cyber Technician"]),
            ("client", ["Customer", "SS97 Cyber Client"]),
            ("otherclient", ["Customer", "SS97 Cyber Client"]),
            ("none", []),
        ]
        for label, roles in configs:
            user = f"cyber-{suffix}-{label}@example.invalid"
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": user,
                    "first_name": label,
                    "send_welcome_email": 0,
                    "roles": [{"role": role} for role in roles],
                }
            ).insert()
            setattr(cls, label, user)
            cls.users.append(user)
        cls.customers = []
        for index, user in enumerate((cls.client, cls.otherclient)):
            doc = frappe.get_doc(
                {
                    "doctype": "Customer",
                    "customer_name": f"Cyber lab {suffix} {index}",
                    "customer_type": "Company",
                    "portal_users": [{"user": user}],
                }
            ).insert()
            cls.customers.append(doc.name)
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        frappe.db.rollback()
        for customer in cls.customers:
            frappe.delete_doc("Customer", customer)
        for user in cls.users:
            frappe.delete_doc("User", user)
        frappe.db.commit()

    def setUp(self):
        frappe.set_user(self.manager)
        self.a, self.b = self.customers
        self.company_a = frappe.get_doc(
            {
                "doctype": "SS97 Cyber Company",
                "customer": self.a,
                "members": [{"user": self.tech, "responsibility": "Technician"}],
            }
        ).insert()
        self.company_b = frappe.get_doc(
            {
                "doctype": "SS97 Cyber Company",
                "customer": self.b,
                "members": [{"user": self.othertech, "responsibility": "Technician"}],
            }
        ).insert()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()
        frappe.clear_cache()

    def asset(self, customer=None, **values):
        return frappe.get_doc(
            dict(
                doctype="SS97 Cyber Asset",
                customer=customer or self.a,
                asset_name="Synthetic laptop",
                asset_type="Computer",
                **values,
            )
        ).insert()

    def incident(self, **values):
        return frappe.get_doc(
            dict(
                doctype="SS97 Cyber Incident",
                customer=self.a,
                title="Synthetic incident",
                **values,
            )
        ).insert()

    def test_company_links_existing_customer_and_contract_scope(self):
        self.assertEqual(self.company_a.customer, self.a)
        self.assertEqual(
            frappe.db.count("SS97 Cyber Company", {"customer": ["in", self.customers]}),
            2,
        )
        self.company_a.authorization_status = "Granted"
        with self.assertRaises(frappe.ValidationError):
            self.company_a.save()
        self.company_a.reload()
        self.company_a.authorization_status = "Granted"
        self.company_a.authorization_reference = (
            "synthetic signed authorization reference"
        )
        self.company_a.save()

    def test_client_document_and_list_isolation(self):
        asset_a, asset_b = self.asset(), self.asset(self.b)
        frappe.set_user(self.client)
        self.assertTrue(frappe.has_permission("SS97 Cyber Asset", doc=asset_a))
        self.assertFalse(frappe.has_permission("SS97 Cyber Asset", doc=asset_b))
        self.assertEqual(
            [r.name for r in frappe.get_list("SS97 Cyber Asset")], [asset_a.name]
        )
        with self.assertRaises(frappe.PermissionError):
            asset_b.check_permission("read")
        with self.assertRaises(frappe.PermissionError):
            api.dashboard(self.b)

    def test_client_cannot_write_even_with_native_permission_bypass(self):
        frappe.set_user(self.client)
        with self.assertRaises(frappe.PermissionError):
            self.asset()
        with self.assertRaises(frappe.PermissionError):
            frappe.get_doc(
                {
                    "doctype": "SS97 Cyber Asset",
                    "customer": self.a,
                    "asset_name": "Denied",
                    "asset_type": "Server",
                }
            ).insert(ignore_permissions=True)

    def test_guest_and_unprivileged_denied(self):
        for user in ("Guest", self.none):
            frappe.set_user(user)
            with self.assertRaises(frappe.PermissionError):
                api.dashboard(self.a)

    def test_technician_scoped_asset_creation(self):
        frappe.set_user(self.tech)
        row = api.create_record(
            "asset",
            {"customer": self.a, "asset_name": "Demo server", "asset_type": "Server"},
        )
        self.assertTrue(frappe.db.exists("SS97 Cyber Asset", row["name"]))
        with self.assertRaises(frappe.PermissionError):
            self.asset(self.b)

    def test_disabled_user_loses_access(self):
        frappe.db.set_value("User", self.tech, "enabled", 0)
        frappe.set_user(self.tech)
        with self.assertRaises(frappe.PermissionError):
            api.dashboard(self.a)

    def test_membership_revocation_removes_access(self):
        self.company_a.members = []
        self.company_a.save()
        frappe.set_user(self.tech)
        with self.assertRaises(frappe.PermissionError):
            api.dashboard(self.a)

    def test_technician_cannot_self_grant_company_membership(self):
        frappe.set_user(self.tech)
        self.company_b.append(
            "members", {"user": self.tech, "responsibility": "Technician"}
        )
        with self.assertRaises(frappe.PermissionError):
            self.company_b.save(ignore_permissions=True)

    def test_customer_reparenting_denied(self):
        row = self.asset()
        row.customer = self.b
        with self.assertRaises(frappe.PermissionError):
            row.save()

    def test_audit_questionnaire_completion(self):
        frappe.set_user(self.tech)
        result = api.create_record(
            "audit",
            {
                "customer": self.a,
                "title": "Baseline",
                "checks": [{"question": "Backups tested?", "result": "Not checked"}],
            },
        )
        doc = frappe.get_doc("SS97 Cyber Audit", result["name"])
        doc.status = "Completed"
        with self.assertRaises(frappe.ValidationError):
            doc.save()
        doc.reload()
        doc.status = "Completed"
        doc.checks[0].result = "Fail"
        doc.save()
        self.assertIsNotNone(doc.completed_at)

    def test_cross_customer_asset_and_audit_links_denied(self):
        asset_b = self.asset(self.b)
        with self.assertRaises(frappe.PermissionError):
            api.create_record(
                "audit", {"customer": self.a, "title": "Denied", "asset": asset_b.name}
            )

    def test_risk_recommendation_by_severity(self):
        row = api.create_record(
            "risk",
            {"customer": self.a, "title": "Unpatched server", "severity": "Critical"},
        )
        doc = frappe.get_doc("SS97 Cyber Risk", row["name"])
        self.assertIn("Escalate immediately", doc.recommendation)
        doc.severity = "Low"
        doc.save()
        self.assertIn("Plan a corrective action", doc.recommendation)

    def test_incident_assignment_requires_manager_and_company_membership(self):
        doc = self.incident()
        with self.assertRaises(frappe.PermissionError):
            api.assign_incident(doc.name, self.othertech, str(doc.modified))
        result = api.assign_incident(doc.name, self.tech, str(doc.modified))
        frappe.set_user(self.tech)
        with self.assertRaises(frappe.PermissionError):
            api.assign_incident(doc.name, self.tech, result["modified"])

    def test_incident_lifecycle_resolution_and_history(self):
        doc = self.incident()
        result = api.assign_incident(doc.name, self.tech, str(doc.modified))
        frappe.set_user(self.tech)
        with self.assertRaises(frappe.ValidationError):
            api.transition_incident(doc.name, "Closed", result["modified"])
        result = api.transition_incident(doc.name, "Investigating", result["modified"])
        with self.assertRaises(frappe.ValidationError):
            api.transition_incident(doc.name, "Resolved", result["modified"])
        result = api.transition_incident(
            doc.name, "Resolved", result["modified"], "Synthetic remediation verified"
        )
        result = api.transition_incident(doc.name, "Closed", result["modified"])
        self.assertEqual(result["status"], "Closed")
        self.assertGreaterEqual(
            frappe.db.count("SS97 Cyber Event", {"record_name": doc.name}), 5
        )

    def test_unassigned_technician_cannot_change_incident(self):
        doc = self.incident()
        frappe.set_user(self.tech)
        with self.assertRaises(frappe.PermissionError):
            api.transition_incident(doc.name, "Investigating", str(doc.modified))

    def test_incident_native_update_cannot_change_assignee(self):
        doc = self.incident(assigned_to=self.tech)
        frappe.set_user(self.tech)
        doc.assigned_to = self.othertech
        with self.assertRaises(frappe.PermissionError):
            doc.save()

    def test_issue_link_reuses_native_ticket_and_rejects_other_customer(self):
        frappe.set_user("Administrator")
        issue = frappe.get_doc(
            {"doctype": "Issue", "subject": "Synthetic cyber link", "customer": self.b}
        ).insert()
        frappe.set_user(self.manager)
        with self.assertRaises(frappe.PermissionError):
            self.incident(issue=issue.name)
        issue.customer = self.a
        frappe.set_user("Administrator")
        issue.save()
        frappe.set_user(self.manager)
        self.assertEqual(self.incident(issue=issue.name).issue, issue.name)

    def test_dashboard_calculations_and_backup_evidence(self):
        self.asset()
        self.asset(
            backup_state="Verified",
            backup_checked_at=frappe.utils.now_datetime(),
            backup_evidence="Lab restore reference",
        )
        api.create_record(
            "risk", {"customer": self.a, "title": "Risk", "severity": "High"}
        )
        self.incident(severity="Critical")
        self.asset(self.b)
        frappe.set_user(self.client)
        values = api.dashboard(self.a)
        self.assertEqual(
            (
                values["equipment"],
                values["open_risks"],
                values["critical_incidents"],
                values["pending_actions"],
            ),
            (2, 1, 1, 1),
        )
        self.assertEqual(values["backups"]["Verified"], 1)
        self.assertEqual(values["backups"]["Unknown"], 1)

    def test_backup_cannot_be_verified_without_evidence(self):
        with self.assertRaises(frappe.ValidationError):
            self.asset(backup_state="Verified")

    def test_events_cannot_be_forged_updated_or_deleted(self):
        with self.assertRaises(frappe.PermissionError):
            frappe.get_doc({"doctype": "SS97 Cyber Event", "customer": self.a}).insert(
                ignore_permissions=True
            )
        event = frappe.get_doc("SS97 Cyber Event", {"record_name": self.company_a.name})
        frappe.set_user("Administrator")
        event.operation = "forged"
        with self.assertRaises(frappe.PermissionError):
            event.save(ignore_permissions=True)
        with self.assertRaises(frappe.PermissionError):
            frappe.delete_doc(event.doctype, event.name, ignore_permissions=True)

    def test_payload_rejects_permission_bypass_and_questionnaire_injection(self):
        with self.assertRaises(frappe.ValidationError):
            api.create_record(
                "asset",
                {"customer": self.a, "asset_name": "x", "ignore_permissions": True},
            )
        with self.assertRaises(frappe.ValidationError):
            api.create_record(
                "audit",
                {
                    "customer": self.a,
                    "title": "x",
                    "checks": [{"doctype": "User", "email": "bad@example.invalid"}],
                },
            )

    def test_director_dashboard_access(self):
        frappe.set_user(self.director)
        self.assertEqual(api.dashboard(self.b)["equipment"], 0)

    def test_stale_incident_update_is_rejected(self):
        doc = self.incident(assigned_to=self.tech)
        revision = str(doc.modified)
        frappe.set_user(self.tech)
        api.transition_incident(doc.name, "Investigating", revision)
        with self.assertRaises(frappe.TimestampMismatchError):
            api.transition_incident(doc.name, "Contained", revision)

    def test_disabled_role_blocks_access_and_queries(self):
        frappe.db.set_value("Role", "SS97 Cyber Technician", "disabled", 1)
        frappe.set_user(self.tech)
        with self.assertRaises(frappe.PermissionError):
            api.dashboard(self.a)
        self.assertEqual(frappe.get_list("SS97 Cyber Asset"), [])

    def test_all_customer_scoped_doctypes_use_native_read_guards(self):
        self.asset(self.b)
        self.incident()
        frappe.set_user(self.client)
        for dt in (
            dt
            for dt in access.DOCTYPES
            if dt not in ("SS97 Cyber Wazuh Config", "SS97 Cyber Sync Run")
        ):
            for row in frappe.get_list(dt, fields=["name", "customer"]):
                self.assertEqual(row.customer, self.a)
        frappe.set_user(self.otherclient)
        for dt in (
            dt
            for dt in access.DOCTYPES
            if dt not in ("SS97 Cyber Wazuh Config", "SS97 Cyber Sync Run")
        ):
            for row in frappe.get_list(dt, fields=["name", "customer"]):
                self.assertEqual(row.customer, self.b)

    def test_questionnaire_unknown_results_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            api.create_record(
                "audit",
                {
                    "customer": self.a,
                    "title": "x",
                    "checks": [{"question": "MFA?", "result": "Invented"}],
                },
            )

    def test_mixed_client_technician_roles_do_not_grant_membership(self):
        frappe.set_user("Administrator")
        user = frappe.get_doc("User", self.client)
        user.add_roles("SS97 Cyber Technician")
        frappe.set_user(self.client)
        self.assertEqual(api.dashboard(self.a)["equipment"], 0)
        with self.assertRaises(frappe.PermissionError):
            self.asset()

    def test_audit_completion_timestamp_is_server_derived(self):
        doc = frappe.get_doc(
            {
                "doctype": "SS97 Cyber Audit",
                "customer": self.a,
                "title": "Synthetic timestamp",
                "completed_at": "2000-01-01 00:00:00",
            }
        ).insert()
        self.assertIsNone(doc.completed_at)
        doc.status = "Completed"
        doc.append("checks", {"question": "Backups?", "result": "Pass"})
        doc.completed_at = "2000-01-01 00:00:00"
        doc.save()
        self.assertGreater(
            frappe.utils.get_datetime(doc.completed_at),
            frappe.utils.get_datetime("2020-01-01"),
        )

    def test_unassigned_incident_validation_rejects_permission_bypass(self):
        doc = self.incident()
        frappe.set_user(self.tech)
        doc.status = "Investigating"
        with self.assertRaises(frappe.PermissionError):
            doc.save(ignore_permissions=True)

    def test_foreign_questionnaire_row_cannot_be_reparented(self):
        foreign = frappe.get_doc(
            {
                "doctype": "SS97 Cyber Audit",
                "customer": self.b,
                "title": "Foreign audit",
                "checks": [{"question": "Private question", "result": "Pass"}],
            }
        ).insert()
        own = frappe.get_doc(
            {
                "doctype": "SS97 Cyber Audit",
                "customer": self.a,
                "title": "Own audit",
                "checks": [{"question": "Own question", "result": "Pass"}],
            }
        ).insert()
        frappe.set_user(self.tech)
        own.checks[0].name = foreign.checks[0].name
        with self.assertRaises(frappe.PermissionError):
            own.save()
