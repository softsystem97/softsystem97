"""Real Frappe operations; Wazuh transport and remote engines stay fictional/disconnected."""

import json
import unittest
from unittest.mock import Mock, patch

import frappe

from softsystem97.cyber import api, remote_requests, reports, wazuh_sync, workspace
from softsystem97.cyber.connectors.remote import DisconnectedRemoteEngine
from softsystem97.cyber.connectors.wazuh import (
    ConnectorError,
    checked_origin,
    fetch_alerts,
)
from softsystem97.tests import test_cyber as cyber_tests


class TestCyberOperations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cyber_tests.TestCyber.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        cyber_tests.TestCyber.tearDownClass.__func__(cls)

    asset = cyber_tests.TestCyber.asset
    incident = cyber_tests.TestCyber.incident

    def setUp(self):
        cyber_tests.TestCyber.setUp(self)
        self.old_hosts = frappe.conf.get("ss97_wazuh_allowed_hosts")
        frappe.conf.ss97_wazuh_allowed_hosts = ["indexer.example.invalid"]

    def tearDown(self):
        if self.old_hosts is None:
            frappe.conf.pop("ss97_wazuh_allowed_hosts", None)
        else:
            frappe.conf.ss97_wazuh_allowed_hosts = self.old_hosts
        cyber_tests.TestCyber.tearDown(self)

    def config(self, enabled=1):
        self.company_a.authorization_status = "Granted"
        self.company_a.authorization_reference = "Fictional signed authorization"
        self.company_a.save()
        asset = self.asset()
        return frappe.get_doc(
            {
                "doctype": "SS97 Cyber Wazuh Config",
                "customer": self.a,
                "enabled": enabled,
                "api_url": "https://indexer.example.invalid:9200",
                "username": "fictional-reader",
                "password": "fictional-test-only-password",
                "create_incidents": 1,
                "minimum_level": 12,
                "mappings": [{"agent_id": "001", "asset": asset.name}],
            }
        ).insert()

    def transport(self, level=15, agent="001", event="fictional-event"):
        payload = {
            "hits": {
                "hits": [
                    {
                        "_id": event,
                        "_source": {
                            "timestamp": "2026-10-21T00:00:00Z",
                            "agent": {"id": agent},
                            "rule": {"level": level},
                            "unneeded_secret": "MUST_NOT_BE_STORED",
                        },
                    }
                ]
            }
        }
        response = Mock(status_code=200)
        response.iter_content.return_value = [json.dumps(payload).encode()]
        return Mock(return_value=response)

    def contract(self):
        frappe.set_user("Administrator")
        contract = frappe.get_doc(
            {
                "doctype": "Contract",
                "party_type": "Customer",
                "party_name": self.a,
                "start_date": frappe.utils.add_days(frappe.utils.today(), -1),
                "end_date": frappe.utils.add_days(frappe.utils.today(), 30),
                "contract_terms": "Fictional remote preparation scope",
                "is_signed": 1,
            }
        ).insert()
        # ERPNext derives status; valid active dates and signature must suffice.
        frappe.set_user(self.manager)
        self.company_a.reload()
        self.company_a.contract = contract.name
        self.company_a.authorization_status = "Granted"
        self.company_a.authorization_reference = "Fictional signed consent scope"
        self.company_a.remote_included = 1
        self.company_a.save()
        return contract

    def issue(self, customer=None):
        frappe.set_user("Administrator")
        issue = frappe.get_doc(
            {
                "doctype": "Issue",
                "subject": "Fictional remote request",
                "customer": customer or self.a,
            }
        ).insert()
        frappe.set_user(self.manager)
        return issue

    def prepared(self):
        self.contract()
        issue = self.issue()
        frappe.set_user(self.client)
        result = remote_requests.request(self.a, issue.name)
        frappe.set_user(self.manager)
        doc = frappe.get_doc("SS97 Cyber Remote Request", result["name"])
        return remote_requests.prepare(
            doc.name, self.tech, "Contract", str(doc.modified)
        )

    def test_workspaces_are_role_and_company_scoped(self):
        self.asset()
        self.asset(self.b)
        frappe.set_user(self.client)
        data = workspace.load("client")
        self.assertEqual(data["indicators"]["equipment"], 1)
        self.assertEqual({row.customer for row in data["companies"]}, {self.a})
        with self.assertRaises(frappe.PermissionError):
            workspace.load("direction")
        with self.assertRaises(frappe.PermissionError):
            workspace.load("client", self.b)
        frappe.set_user(self.tech)
        self.assertEqual(workspace.load("technician")["indicators"]["equipment"], 1)
        frappe.set_user(self.director)
        # Other persistent demo companies may exist; filter only this test scope.
        self.assertEqual(
            workspace.load("direction", self.b)["indicators"]["equipment"], 1
        )

    def test_action_assignment_and_permissions(self):
        risk = frappe.get_doc(
            {
                "doctype": "SS97 Cyber Risk",
                "customer": self.a,
                "title": "Fictional action",
            }
        ).insert()
        with self.assertRaises(frappe.PermissionError):
            api.assign_action(risk.name, self.othertech, str(risk.modified))
        risk.reload()
        api.assign_action(
            risk.name, self.tech, str(risk.modified), frappe.utils.today()
        )
        frappe.set_user(self.tech)
        risk.reload()
        risk.status = "In progress"
        risk.action_notes = "Fictional diagnostic"
        risk.save()
        with self.assertRaises(frappe.PermissionError):
            api.assign_action(risk.name, self.tech, str(risk.modified))

    def test_report_generation_approval_and_client_isolation(self):
        self.asset()
        result = reports.generate(self.a, frappe.utils.today(), frappe.utils.today())
        doc = frappe.get_doc("SS97 Cyber Report", result["name"])
        frappe.set_user(self.client)
        with self.assertRaises(frappe.PermissionError):
            reports.detail(doc.name)
        self.assertEqual(frappe.get_list("SS97 Cyber Report"), [])
        frappe.set_user(self.manager)
        reports.approve(doc.name, str(doc.modified))
        frappe.set_user(self.client)
        detail = reports.detail(doc.name)
        self.assertEqual(detail["data"]["indicators"]["equipment"], 1)
        self.assertIn("Unknown", detail["data"]["known_protection"])
        frappe.set_user(self.otherclient)
        with self.assertRaises(frappe.PermissionError):
            reports.detail(doc.name)

    def test_report_snapshot_and_approval_cannot_be_forged(self):
        with self.assertRaises(frappe.PermissionError):
            frappe.get_doc(
                {
                    "doctype": "SS97 Cyber Report",
                    "customer": self.a,
                    "from_date": frappe.utils.today(),
                    "to_date": frappe.utils.today(),
                    "snapshot": "{}",
                }
            ).insert(ignore_permissions=True)
        result = reports.generate(self.a, frappe.utils.today(), frappe.utils.today())
        doc = frappe.get_doc("SS97 Cyber Report", result["name"])
        doc.snapshot = "{}"
        with self.assertRaises(frappe.PermissionError):
            doc.save()

    def test_report_period_validation(self):
        with self.assertRaises(frappe.ValidationError):
            reports.generate(self.a, "2026-12-01", "2026-01-01")
        with self.assertRaises(frappe.ValidationError):
            reports.generate(self.a, "2020-01-01", "2026-01-01")

    def test_wazuh_tls_minimal_fields_and_no_redirects(self):
        transport = self.transport()
        alerts, truncated = fetch_alerts(
            "https://indexer.example.invalid:9200",
            "user",
            "fake",
            "2026-10-20T00:00:00Z",
            ["indexer.example.invalid"],
            transport,
        )
        self.assertEqual(alerts[0].level, 15)
        self.assertFalse(truncated)
        args = transport.call_args.kwargs
        self.assertTrue(args["verify"])
        self.assertFalse(args["allow_redirects"])
        self.assertEqual(
            args["json"]["_source"], ["agent.id", "rule.level", "timestamp"]
        )
        self.assertNotIn("MUST_NOT_BE_STORED", str(alerts))

    def test_wazuh_rejects_unapproved_or_credential_urls(self):
        for url in (
            "http://indexer.example.invalid",
            "https://u:p@indexer.example.invalid",
            "https://indexer.example.invalid?q=secret",
            "https://127.0.0.1",
            "https://169.254.169.254",
            "https://other.invalid",
        ):
            with self.assertRaises(ConnectorError):
                checked_origin(
                    url, ["indexer.example.invalid", "127.0.0.1", "169.254.169.254"]
                )

    def test_wazuh_sync_deduplicates_with_real_native_ledger(self):
        config = self.config()
        first = wazuh_sync.synchronize(
            config.name, "2026-10-20T00:00:00Z", self.transport()
        )
        second = wazuh_sync.synchronize(
            config.name, "2026-10-20T00:00:00Z", self.transport()
        )
        self.assertEqual((first["accepted"], second["duplicates"]), (1, 1))
        self.assertEqual(
            frappe.db.count("SS97 Cyber Incident", {"customer": self.a}), 1
        )
        self.assertEqual(
            frappe.db.count("SS97 Cyber Sync Event", {"customer": self.a}), 1
        )
        event = frappe.get_doc("SS97 Cyber Sync Event", {"configuration": config.name})
        self.assertNotIn("MUST_NOT_BE_STORED", str(event.as_dict()))

    def test_wazuh_unknown_agent_cannot_select_customer_or_asset(self):
        config = self.config()
        result = wazuh_sync.synchronize(
            config.name,
            "2026-10-20T00:00:00Z",
            self.transport(agent="other-company-agent"),
        )
        self.assertEqual((result["ignored"], result["accepted"]), (1, 0))
        self.assertEqual(
            frappe.db.count("SS97 Cyber Incident", {"customer": self.a}), 0
        )

    def test_wazuh_disabled_and_revoked_authorization_prevent_transport(self):
        config = self.config(enabled=0)
        transport = self.transport()
        with self.assertRaises(frappe.PermissionError):
            wazuh_sync.synchronize(config.name, "2026-10-20T00:00:00Z", transport)
        transport.assert_not_called()
        config.enabled = 1
        config.save()
        self.company_a.reload()
        self.company_a.authorization_status = "Revoked"
        self.company_a.save()
        with self.assertRaises(frappe.PermissionError):
            wazuh_sync.synchronize(config.name, "2026-10-20T00:00:00Z", transport)
        transport.assert_not_called()

    def test_wazuh_error_is_redacted_and_batch_rolls_back(self):
        config = self.config()
        transport = Mock(side_effect=RuntimeError("SECRET_MUST_NOT_LEAK"))
        result = wazuh_sync.synchronize(config.name, "2026-10-20T00:00:00Z", transport)
        self.assertEqual(result["status"], "Error")
        run = frappe.get_doc("SS97 Cyber Sync Run", result["run"])
        self.assertNotIn("SECRET_MUST_NOT_LEAK", str(run.as_dict()))
        self.assertEqual(
            frappe.db.count("SS97 Cyber Sync Event", {"customer": self.a}), 0
        )

    def test_wazuh_configuration_and_sync_not_client_accessible(self):
        config = self.config()
        frappe.set_user(self.client)
        with self.assertRaises(frappe.PermissionError):
            config.check_permission("read")
        with self.assertRaises(frappe.PermissionError):
            frappe.get_list("SS97 Cyber Wazuh Config")
        with self.assertRaises(frappe.PermissionError):
            wazuh_sync.synchronize(
                config.name, "2026-10-20T00:00:00Z", self.transport()
            )

    def test_wazuh_mapping_cannot_reference_another_company_asset(self):
        foreign = self.asset(self.b)
        config = self.config(enabled=0)
        config.mappings[0].asset = foreign.name
        with self.assertRaises(frappe.PermissionError):
            config.save()

    def test_remote_request_cannot_reference_foreign_ticket(self):
        issue = self.issue(self.b)
        frappe.set_user(self.client)
        with self.assertRaises(frappe.PermissionError):
            remote_requests.request(self.a, issue.name)

    def test_remote_request_without_billing_cannot_prepare(self):
        issue = self.issue()
        frappe.set_user(self.client)
        result = remote_requests.request(self.a, issue.name)
        frappe.set_user(self.manager)
        doc = frappe.get_doc("SS97 Cyber Remote Request", result["name"])
        with self.assertRaises(frappe.PermissionError):
            remote_requests.prepare(doc.name, self.tech, "Contract", str(doc.modified))

    def test_remote_consent_revoke_close_without_engine(self):
        result = self.prepared()
        frappe.set_user(self.tech)
        with self.assertRaises(frappe.PermissionError):
            remote_requests.transition(result["name"], "Consented", result["modified"])
        frappe.set_user(self.client)
        result = remote_requests.transition(
            result["name"], "Consented", result["modified"]
        )
        self.assertFalse(result["can_start"])
        doc = frappe.get_doc("SS97 Cyber Remote Request", result["name"])
        self.assertEqual(doc.consented_by, self.client)
        self.assertEqual(doc.duration_seconds, 0)
        result = remote_requests.transition(doc.name, "Revoked", result["modified"])
        frappe.set_user(self.manager)
        result = remote_requests.transition(
            doc.name,
            "Closed",
            result["modified"],
            "Preparation closed; no actual remote session",
        )
        self.assertEqual(result["state"], "Closed")
        with self.assertRaises(RuntimeError):
            DisconnectedRemoteEngine().start("anything")

    def test_remote_consent_metadata_cannot_be_spoofed(self):
        result = self.prepared()
        frappe.set_user(self.client)
        result = remote_requests.transition(
            result["name"], "Consented", result["modified"]
        )
        doc = frappe.get_doc("SS97 Cyber Remote Request", result["name"])
        actual = doc.consented_at
        doc.consented_by = self.otherclient
        doc.consented_at = "2000-01-01"
        doc.duration_seconds = 3600
        doc.save()
        self.assertEqual(doc.consented_by, self.client)
        self.assertEqual(str(doc.consented_at), str(actual))
        self.assertEqual(doc.duration_seconds, 0)

    def test_remote_foreign_client_and_ticket_status_are_untouched(self):
        result = self.prepared()
        doc = frappe.get_doc("SS97 Cyber Remote Request", result["name"])
        issue_status = frappe.db.get_value("Issue", doc.issue, "status")
        frappe.set_user(self.otherclient)
        with self.assertRaises(frappe.PermissionError):
            remote_requests.transition(doc.name, "Consented", result["modified"])
        self.assertEqual(
            frappe.db.get_value("Issue", doc.issue, "status"), issue_status
        )

    def test_wazuh_concurrent_deliveries_create_one_incident(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor

        config = self.config()
        frappe.db.commit()  # Separate native connections must see synthetic fixtures.
        site, sites_path = frappe.local.site, frappe.local.sites_path
        barrier = threading.Barrier(2)

        def deliver():
            frappe.init(site=site, sites_path=sites_path)
            frappe.connect()
            frappe.set_user(self.manager)
            frappe.conf.ss97_wazuh_allowed_hosts = ["indexer.example.invalid"]
            try:
                barrier.wait(timeout=10)
                for _ in range(4):
                    try:
                        result = wazuh_sync.synchronize(
                            config.name, "2026-10-20T00:00:00Z", self.transport()
                        )
                        frappe.db.commit()
                        return result
                    except wazuh_sync.SyncRetryConflict:
                        frappe.db.rollback()
                raise AssertionError("Concurrent imports failed to converge")
            finally:
                frappe.db.rollback()
                frappe.destroy()

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: deliver(), range(2)))
            frappe.db.rollback()
            self.assertEqual(sum(r["accepted"] for r in results), 1)
            self.assertEqual(sum(r["duplicates"] for r in results), 1)
            self.assertTrue(all(r["status"] == "Success" for r in results))
            self.assertEqual(
                frappe.db.count("SS97 Cyber Incident", {"customer": self.a}), 1
            )
        finally:
            frappe.db.rollback()
            frappe.set_user("Administrator")
            # Fixture-only deletion; production controllers still prohibit deletion.
            for child in ("SS97 Cyber Member", "SS97 Cyber Agent Map"):
                parents = [self.company_a.name, self.company_b.name, config.name]
                frappe.db.delete(child, {"parent": ["in", parents]})
            from softsystem97.cyber.permissions import DOCTYPES

            for dt in DOCTYPES:
                frappe.db.delete(dt, {"customer": ["in", self.customers]})
            frappe.db.commit()

    def test_wazuh_malformed_alert_cannot_create_records(self):
        config = self.config()
        response = Mock(status_code=200)
        response.iter_content.return_value = [
            b'{"hits":{"hits":[{"_id":"x","_source":{}}]}}'
        ]
        result = wazuh_sync.synchronize(
            config.name, "2026-10-20T00:00:00Z", Mock(return_value=response)
        )
        self.assertEqual(result["status"], "Error")
        self.assertEqual(
            frappe.db.count("SS97 Cyber Incident", {"customer": self.a}), 0
        )

    def test_wazuh_full_batch_is_explicitly_truncated(self):
        response = Mock(status_code=200)
        rows = [
            {
                "_id": str(n),
                "_source": {
                    "agent": {"id": "001"},
                    "rule": {"level": 1},
                    "timestamp": "2026-10-21T00:00:00Z",
                },
            }
            for n in range(100)
        ]
        response.iter_content.return_value = [
            json.dumps({"hits": {"hits": rows}}).encode()
        ]
        alerts, truncated = fetch_alerts(
            "https://indexer.example.invalid",
            "u",
            "fake",
            "2026-10-20T00:00:00Z",
            ["indexer.example.invalid"],
            Mock(return_value=response),
        )
        self.assertEqual(len(alerts), 100)
        self.assertTrue(truncated)

    def test_remote_contract_revocation_blocks_customer_consent(self):
        result = self.prepared()
        self.company_a.reload()
        self.company_a.authorization_status = "Revoked"
        self.company_a.save()
        frappe.set_user(self.client)
        with self.assertRaises(frappe.PermissionError):
            remote_requests.transition(result["name"], "Consented", result["modified"])

    def test_remote_invoice_eligibility_is_server_checked(self):
        from softsystem97.cyber.operations_model import billing_verified

        self.company_a.authorization_status = "Granted"
        self.company_a.authorization_reference = "Fictional authorized scope"
        self.company_a.remote_included = 1
        self.company_a.save()
        original = frappe.db.get_value
        valid = frappe._dict(
            customer=self.a,
            docstatus=1,
            outstanding_amount=0,
            grand_total=100,
            is_return=0,
        )

        def read(*args, **kwargs):
            doctype = args[0] if args else kwargs.get("doctype")
            return valid if doctype == "Sales Invoice" else original(*args, **kwargs)

        with patch.object(frappe.db, "get_value", side_effect=read):
            self.assertTrue(billing_verified(self.a, "Invoice", "FICTITIOUS-INVOICE"))
            for field, value in [
                ("customer", self.b),
                ("docstatus", 0),
                ("docstatus", 2),
                ("outstanding_amount", 1),
                ("grand_total", 0),
                ("is_return", 1),
            ]:
                before = valid[field]
                valid[field] = value
                self.assertFalse(
                    billing_verified(self.a, "Invoice", "FICTITIOUS-INVOICE")
                )
                valid[field] = before

    def test_remote_consent_can_be_withdrawn_after_technician_is_disabled(self):
        result = self.prepared()
        frappe.set_user(self.client)
        result = remote_requests.transition(
            result["name"], "Consented", result["modified"]
        )
        frappe.set_user("Administrator")
        frappe.db.set_value("User", self.tech, "enabled", 0)
        frappe.set_user(self.client)
        result = remote_requests.transition(
            result["name"], "Revoked", result["modified"]
        )
        self.assertEqual(result["state"], "Revoked")
        self.assertFalse(result["can_start"])
