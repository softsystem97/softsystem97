"""Recovered registry and cockpit source tests. Never execute deployment scripts.

With --frappe-site, use native RestrictedPython compilation, but fictional Issue,
notification and payment facades. The native guard has separate Frappe DB tests.
"""

import ast
import os
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from integrations.ss97_technician_operations import cockpit_start_api as cockpit
from integrations.ss97_technician_operations import (
    technician_portal_registry as registry,
)


class Denied(Exception):
    pass


class Record(dict):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return self.get(name)

    def __setattr__(self, name, value):
        self[name] = value

    def save(self, **kwargs):
        self.saved += 1


class TestRecoveredPortal(unittest.TestCase):
    def script(self):
        provider = ModuleType("integrations.ss97_gwen_notifications.wa_block")
        provider.WA_FUNCS = ""  # Explicitly fictional; no WhatsApp validation claimed.
        with patch.dict(sys.modules, {provider.__name__: provider}):
            return cockpit.api_script_source()

    def facade(self, action="start", **values):
        doc = Record(
            name="SYNTHETIC-ISSUE",
            status="Open",
            saved=0,
            ss97_technician="tech@example.invalid",
            ss97_ticket_status="Accepté par le technicien",
            ss97_accepted_on="2026-10-21 10:00:00",
            ss97_checklist_pre_done=1,
            meta=SimpleNamespace(has_field=lambda key: True),
            **values,
        )
        f = SimpleNamespace(
            form_dict={"action": action, "issue": doc.name},
            session=SimpleNamespace(user="tech@example.invalid"),
            response={},
            call=Mock(return_value=True),
            get_doc=Mock(return_value=doc),
            get_all=Mock(
                side_effect=lambda dt, **kw: (
                    [Record(role="SS97 Technician")] if dt == "Has Role" else []
                )
            ),
            db=SimpleNamespace(
                exists=Mock(return_value=False),
                get_value=Mock(return_value="Fictional technician"),
                commit=Mock(side_effect=AssertionError("No internal commit")),
            ),
            utils=SimpleNamespace(
                now=lambda: "2026-10-21 10:05:00", time_diff_in_seconds=lambda *args: 60
            ),
        )
        return f, doc

    def execute(self, facade):
        exec(compile(self.script(), "recovered-cockpit", "exec"), {"frappe": facade})  # noqa: S102 -- repo-owned test source
        return facade.response.get("message")

    def test_internal_notification_recipient_is_current_authorized_actor(self):
        source = self.script()
        self.assertIn('"for_user": user', source)
        self.assertIn('"owner": user', source)
        self.assertNotIn('"for_user": "', source)

    def test_registry_lists_original_routes_without_importing_missing_builders(self):
        with patch.object(
            registry, "import_module", side_effect=AssertionError("no eager imports")
        ):
            rows = registry.deploy_specs()
        self.assertEqual(len(rows), 30)
        self.assertIn("espace-technicien/tickets", [route for _, route, _ in rows])

    def test_tickets_route_reuses_exact_received_builder(self):
        build = next(
            builder
            for _, route, builder in registry.deploy_specs()
            if route == "espace-technicien/tickets"
        )
        page = Mock(return_value="<main>fixture</main>")
        portal = object()

        def resolve(name):
            if name == "integrations.ss97_technician_etape6.deploy":
                return SimpleNamespace(page_tickets=page)
            self.assertEqual(name, "integrations.ss97_technician_operations.portals")
            return portal

        with patch.object(registry, "import_module", side_effect=resolve):
            self.assertEqual(build(), "<main>fixture</main>")
        page.assert_called_once_with(portal)

    def test_real_commercial_builder_renders_scoped_adapter_without_development_page(self):
        build = next(
            builder
            for _, route, builder in registry.deploy_specs()
            if route == "espace-technicien/tickets"
        )
        html = build()
        self.assertIn('ss97-ticket-rows', html)
        self.assertIn('ticket_bridge.api.', html)
        self.assertNotIn('frappe.client.save', html)

    def test_generator_preserves_legacy_export_and_stays_disabled(self):
        provider = ModuleType("integrations.ss97_gwen_notifications.wa_block")
        provider.WA_FUNCS = ""
        with patch.dict(sys.modules, {provider.__name__: provider}):
            doc = cockpit.server_script_doc()
            self.assertEqual(cockpit.API_SCRIPT, doc["script"])
        self.assertEqual(doc["allow_guest"], 0)
        self.assertEqual(doc["disabled"], 1)

    def test_missing_notification_dependency_never_gets_silent_fallback(self):
        with self.assertRaises(ModuleNotFoundError):
            cockpit.api_script_source()

    def test_guard_denial_precedes_any_issue_read_or_notification(self):
        f, doc = self.facade()
        f.call.side_effect = Denied("authorization required")
        with self.assertRaises(Denied):
            self.execute(f)
        f.get_doc.assert_not_called()
        f.get_all.assert_not_called()
        self.assertEqual(doc.saved, 0)

    def test_payment_markers_never_substitute_server_authorization(self):
        node = next(
            n
            for n in ast.parse(cockpit.SCRIPT_BODY).body
            if isinstance(n, ast.FunctionDef) and n.name == "paid_ok"
        )
        fn_source = ast.get_source_segment(cockpit.SCRIPT_BODY, node)
        for marker in ("", "n/a", "test", "pending", "unpaid", "refunded"):
            f, doc = self.facade(
                ss97_payment_status=marker, ss97_payment_ref="FAKE-REFERENCE"
            )
            f.call.side_effect = Denied("payment proof absent")
            namespace = {"frappe": f}
            exec(fn_source, namespace)  # noqa: S102 -- fixed function from reviewed test source
            with self.assertRaises(Denied):
                namespace["paid_ok"](doc)

    def test_start_never_self_assigns_or_auto_completes_checklist(self):
        node = next(
            n
            for n in ast.parse(cockpit.SCRIPT_BODY).body
            if isinstance(n, ast.FunctionDef) and n.name == "ensure_assignment"
        )
        namespace = {"user": "tech@example.invalid", "user_is_technician": lambda: True}
        exec(ast.get_source_segment(cockpit.SCRIPT_BODY, node), namespace)  # noqa: S102 -- reviewed function fixture
        doc = Record(ss97_technician="")
        self.assertFalse(namespace["ensure_assignment"](doc)["ok"])
        self.assertEqual(doc.ss97_technician, "")
        f, doc = self.facade()
        doc.ss97_checklist_pre_done = 0
        result = self.execute(f)
        self.assertFalse(result["ok"])
        self.assertEqual(doc.ss97_checklist_pre_done, 0)
        self.assertEqual(doc.saved, 0)

    def test_authorized_start_updates_native_status_without_early_commit(self):
        f, doc = self.facade()
        result = self.execute(f)
        self.assertTrue(result["ok"])
        self.assertEqual(doc.status, "Open")
        self.assertEqual(doc.ss97_ticket_status, "Intervention en cours")
        self.assertEqual(doc.saved, 1)
        f.db.commit.assert_not_called()

    def test_complete_ignores_forged_duration_and_test_closure_marker(self):
        f, doc = self.facade(
            action="complete",
            ss97_intervention_report="Synthetic report",
            ss97_diagnostic="Synthetic diagnosis",
            ss97_work_seconds=30,
            ss97_timer_resumed_on="2026-10-21 10:04:00",
            ss97_payment_status="test",
        )
        doc.ss97_ticket_status = "Validation administrateur en attente"
        f.form_dict["work_seconds"] = "999999"
        result = self.execute(f)
        self.assertTrue(result["ok"])
        self.assertEqual(doc.ss97_work_seconds, 90)
        self.assertEqual(doc.ss97_ticket_status, "Intervention terminée")
        self.assertEqual(doc.status, "Resolved")
        f.db.commit.assert_not_called()

    def test_remote_close_never_echoes_or_logs_remote_code(self):
        f, doc = self.facade(
            action="close_remote", ss97_remote_session_id="SENSITIVE_REMOTE_CODE"
        )
        result = self.execute(f)
        self.assertTrue(result["ok"])
        self.assertIs(result["revoked"], True)
        self.assertNotIn("SENSITIVE_REMOTE_CODE", doc.ss97_proof_log)
        self.assertEqual(doc.ss97_remote_session_id, "")

    def test_submit_close_requires_existing_report_diagnosis_and_checklist(self):
        f, doc = self.facade(action="submit_close")
        result = self.execute(f)
        self.assertFalse(result["ok"])
        self.assertEqual(doc.saved, 0)

    def test_submit_close_only_requests_administrator_validation(self):
        f, doc = self.facade(
            action="submit_close",
            ss97_diagnostic="Synthetic diagnosis",
            ss97_intervention_report="Synthetic report",
            ss97_checklist_close_done=1,
        )
        result = self.execute(f)
        self.assertTrue(result["ok"])
        self.assertEqual(doc.ss97_ticket_status, "Validation administrateur en attente")
        self.assertEqual(doc.status, "Resolved")
        f.db.commit.assert_not_called()


if __name__ == "__main__":
    if "--frappe-site" not in sys.argv:
        unittest.main(verbosity=2)
    else:
        i = sys.argv.index("--frappe-site")
        site = sys.argv[i + 1]
        del sys.argv[i : i + 2]
        if not site.startswith(("audit.", "test_")):
            raise SystemExit("Disposable site required")
        import frappe

        sites = Path.cwd() / "sites"
        os.chdir(sites)
        frappe.init(site=site, sites_path=str(sites))
        frappe.connect()
        from frappe.utils.safe_exec import safe_exec

        try:
            if not frappe.conf.allow_tests:
                raise SystemExit("allow_tests required")

            def restricted(self, facade):
                safe_exec(self.script(), _globals={"frappe": facade})
                return facade.response.get("message")

            TestRecoveredPortal.execute = restricted
            with patch(
                "frappe.utils.safe_exec.is_safe_exec_enabled", return_value=True
            ):
                program = unittest.main(verbosity=2, exit=False)
            raise SystemExit(0 if program.result.wasSuccessful() else 1)
        finally:
            frappe.db.rollback()
            frappe.destroy()
