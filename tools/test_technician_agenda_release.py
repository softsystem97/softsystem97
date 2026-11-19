"""Offline contract tests for the new read-only technician agenda."""

import importlib.util
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "softsystem97" / "portal" / "technician_agenda.py"
JS = ROOT / "softsystem97" / "public" / "js" / "technician_agenda.js"


class AgendaTests(unittest.TestCase):
    def make_module(self, access, entries=(), columns=True):
        forbidden = type("PermissionError", (Exception,), {})

        def throw(message, exc):
            raise exc(message)

        class Database:
            def __init__(self):
                self.calls = []

            def table_exists(self, doctype):
                return doctype == "Issue"

            def sql(self, query, params, as_dict=False):
                self.calls.append((query, params, as_dict))
                return entries

        database = Database()
        frappe = ModuleType("frappe")
        frappe.db = database
        frappe.session = SimpleNamespace(user="authorized@example.invalid")
        frappe.PermissionError = forbidden
        frappe.throw = throw
        frappe.whitelist = lambda **kwargs: lambda function: function
        frappe.get_meta = lambda doctype: SimpleNamespace(has_field=lambda name: columns)
        package = ModuleType("softsystem97")
        package.__path__ = [str(ROOT / "softsystem97")]
        portal = ModuleType("softsystem97.portal")
        portal.__path__ = [str(ROOT / "softsystem97" / "portal")]
        access_module = ModuleType("softsystem97.portal.technician_access")
        access_module.my_technician_access = lambda: access
        modules = {"frappe": frappe, "softsystem97": package,
                   "softsystem97.portal": portal,
                   "softsystem97.portal.technician_access": access_module}
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location(
                "softsystem97.portal.technician_agenda", API
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        return module, frappe

    def test_guest_and_unqualified_user_cannot_query_records(self):
        for access in (
            {"authenticated": False, "isTechnician": True},
            {"authenticated": True, "isTechnician": False, "isAdmin": False},
        ):
            with self.subTest(access=access):
                module, frappe = self.make_module(access)
                with self.assertRaises(frappe.PermissionError):
                    module.get_my_agenda()
                self.assertEqual(frappe.db.calls, [])

    def test_only_current_session_user_bound_to_query(self):
        rows = [{"name": "ISS-01", "subject": "Test", "status": "Open",
                 "priority": "Medium", "starts_at": "2026-11-19 09:00:00"}]
        module, frappe = self.make_module(
            {"authenticated": True, "isTechnician": True}, entries=rows
        )
        self.assertEqual(module.get_my_agenda(), {"count": 1, "entries": [{
            "ticket": "ISS-01", "subject": "Test", "status": "Open",
            "priority": "Medium", "starts_at": "2026-11-19 09:00:00"
        }]})
        query, params, as_dict = frappe.db.calls[0]
        self.assertIn("ss97_technician = %s", query)
        self.assertIn("ss97_appointment_on IS NOT NULL", query)
        self.assertIn("LIMIT 100", query)
        self.assertEqual(params, ("authorized@example.invalid",))
        self.assertTrue(as_dict)

    def test_missing_custom_field_yields_empty_agenda_not_500(self):
        module, frappe = self.make_module(
            {"authenticated": True, "isAdmin": True}, columns=False
        )
        self.assertEqual(module.get_my_agenda(), {"count": 0, "entries": []})
        self.assertEqual(frappe.db.calls, [])

    def test_browser_script_has_timeout_retry_and_all_four_languages(self):
        subprocess.run(["node", "--check", str(JS)], check=True, capture_output=True)
        source = JS.read_text(encoding="utf-8")
        for code in ("fr:", "en:", "es:", "ht:"):
            self.assertIn(code, source)
        for text in ("AbortController", "12000", "get_my_agenda", "replaceChildren",
                     "encodeURIComponent", "addEventListener('click', load)"):
            self.assertIn(text, source)
        self.assertNotIn("innerHTML", source)


if __name__ == "__main__":
    unittest.main()
