"""Received catalogue and normalizer, no simulated specs/SLA or remote deployment.

Only SDK transport is fictional. Native Frappe schema/actor/payment rules are not
claimed here. No migration, remote client or runtime application setup is needed.
"""

import ast
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integrations.ss97_client_ops.ticket_types import create_typed_ticket
from integrations.ss97_tickets import fix_priority, specs, workflow_logic
from softsystem97.integrations.ticket_bridge import business_policy


class TestReceivedDependencies(unittest.TestCase):
    def test_import_and_preparation_do_not_need_sdk_or_frappe(self):
        code = """
import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.startswith(('migrate_odoo_erpnext', 'frappe')):
        raise AssertionError('Pure preparation must not import SDK or Frappe')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from integrations.ss97_tickets.workflow_logic import prepare_new_issue
assert prepare_new_issue({'priority':'Urgent'})['priority'] == 'Urgent'
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_all_confirmed_priority_labels_agree_with_normalizer(self):
        for label, expected in specs.PRIORITY_MAP.items():
            with self.subTest(label=label):
                self.assertEqual(fix_priority.normalize_priority(label), expected)
                self.assertEqual(
                    fix_priority.normalize_priority(label.lower()), expected
                )
                self.assertEqual(workflow_logic.map_portal_priority(label), expected)

    def test_preparation_uses_real_sla_and_defaults_without_payment_confirmation(self):
        before = datetime.now(timezone.utc)
        original = {"priority": "Urgente"}
        prepared = workflow_logic.prepare_new_issue(original)
        deadline = datetime.strptime(
            prepared["ss97_sla_deadline"], "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=timezone.utc)
        self.assertAlmostEqual((deadline - before).total_seconds(), 2 * 3600, delta=2)
        self.assertEqual(original, {"priority": "Urgente"})
        self.assertEqual(prepared["priority"], "Urgent")
        self.assertEqual(prepared["status"], "Open")
        self.assertEqual(prepared["ss97_ticket_status"], "Nouveau")
        self.assertEqual(prepared["ss97_source"], "Desk")
        self.assertNotIn("ss97_payment_status", prepared)
        self.assertNotIn("ss97_technician", prepared)

    def test_unknown_and_unmapped_states_cannot_silently_reopen_issue(self):
        for status in ("UNKNOWN", "Suspendu — risque sécurité"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                workflow_logic.prepare_new_issue({"ss97_ticket_status": status})
        self.assertEqual(
            workflow_logic.prepare_new_issue({"ss97_ticket_status": "Clôturé"})[
                "status"
            ],
            "Closed",
        )

    def test_declared_edges_do_not_grant_actor_authorization(self):
        self.assertTrue(
            business_policy.is_declared_transition(
                "Affecté au technicien", "Accepté par le technicien"
            )
        )
        self.assertFalse(business_policy.is_declared_transition("Nouveau", "Clôturé"))
        # Exact aliases are not merged to broaden the original graph.
        self.assertFalse(
            business_policy.is_declared_transition(
                "Affecté", "Refusé par le technicien"
            )
        )
        self.assertFalse(
            callable(getattr(business_policy, "authorize_ticket_operation", None))
        )

    def test_conflicting_alias_and_missing_mapping_remain_explicit(self):
        gaps = business_policy.catalogue_gaps()
        self.assertIn("Terminé", gaps["alias_native_conflicts"])
        self.assertIn("Suspendu — risque sécurité", gaps["unmapped_statuses"])
        self.assertFalse(gaps["authorization_provider_available"])

    def test_duplicate_keys_are_removed_without_merging_shadowed_actions(self):
        tree = ast.parse((ROOT / "integrations/ss97_tickets/specs.py").read_text())
        for node in tree.body:
            value = getattr(node, "value", None)
            if isinstance(value, ast.Dict):
                keys = [k.value for k in value.keys if isinstance(k, ast.Constant)]
                self.assertEqual(len(keys), len(set(keys)))
        self.assertNotIn(("Terminer", "Terminé"), specs.STATUS_ACTIONS["En cours"])
        self.assertIn(("Marquer résolu", "Résolu"), specs.STATUS_ACTIONS["En cours"])
        self.assertEqual(
            specs.STATUS_ACTIONS["En attente du client"][0],
            ("Reprendre", "Intervention en cours"),
        )

    def test_typed_creation_uses_actual_received_priorities_and_sla(self):
        client = Mock()
        client.request.return_value = {"data": []}
        client.list_docs.return_value = []
        client.insert.return_value = {"data": {"name": "SYNTHETIC-REAL-SPECS"}}
        result = create_typed_ticket(
            client, customer="Fictional Customer", kind="urgence"
        )
        payload = client.insert.call_args.args[0]
        self.assertTrue(result["ok"])
        self.assertEqual(payload["priority"], "Urgent")
        self.assertEqual(payload["customer"], "Fictional Customer")
        self.assertEqual(payload["doctype"], "Issue")
        self.assertTrue(payload["ss97_sla_deadline"])
        self.assertNotIn("ss97_payment_status", payload)

    def test_restricted_priority_list_never_returns_missing_default(self):
        for allowed in ([], ["High", "Urgent"]):
            with self.subTest(allowed=allowed), self.assertRaises(ValueError):
                fix_priority.normalize_priority("unknown", allowed=allowed)
        self.assertEqual(
            fix_priority.normalize_priority("haute", allowed=["High"]), "High"
        )

    def test_priority_remediation_defaults_to_read_only_preview(self):
        client = Mock()
        client.url = "https://private.invalid?token=SENSITIVE_SENTINEL"
        client.list_docs.return_value = [{"name": "High"}]
        with (
            patch.object(fix_priority, "write_report") as write,
            redirect_stdout(StringIO()),
        ):
            report = fix_priority.run(client=client)
        self.assertEqual(report["mode"], "preview")
        self.assertFalse(report["writes_performed"])
        self.assertNotIn("SENSITIVE_SENTINEL", json.dumps(report))
        client.list_docs.assert_called_once_with(
            "Issue Priority", fields=["name"], limit=50
        )
        client.insert.assert_not_called()
        client.save.assert_not_called()
        client.request.assert_not_called()
        write.assert_not_called()

    def test_test_ticket_creation_requires_separate_explicit_apply_option(self):
        client = Mock()
        with self.assertRaises(ValueError):
            fix_priority.run(client=client, create_test_tickets=True)
        client.assert_not_called()
        client.list_docs.assert_not_called()

    def test_uncertain_priority_insert_is_not_blindly_retried(self):
        client = Mock()
        client.list_docs.return_value = [{"name": p} for p in ("Low", "Medium", "High")]
        client.insert.side_effect = TimeoutError("private transport failure")
        client.request.return_value = {"data": {"name": "Urgent"}}
        report = fix_priority.ensure_issue_priorities(client)
        client.insert.assert_called_once()
        self.assertEqual(report["Urgent"], "exists_after_error")

    def test_upstream_priority_errors_are_not_copied_to_report(self):
        client = Mock()
        client.list_docs.return_value = []
        client.insert.side_effect = RuntimeError("SENSITIVE_SENTINEL")
        report = fix_priority.ensure_issue_priorities(client)
        self.assertNotIn("SENSITIVE_SENTINEL", json.dumps(report))
        self.assertTrue(
            all(v == "err:priority_creation_failed" for v in report.values())
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
