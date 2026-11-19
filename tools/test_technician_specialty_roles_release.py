"""Migration regression checks for least-privilege N2/N3/N4 roles."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


SOURCE = Path(__file__).resolve().parents[1] / "softsystem97/patches/v1_0/ss97_specialty_roles.py"
PATCHES = SOURCE.parents[2] / "patches.txt"


class SpecialtyRolesMigrationTests(unittest.TestCase):
    def test_installs_only_three_web_roles_without_assignments(self):
        created = []
        frappe = types.ModuleType("frappe")
        frappe.db = types.SimpleNamespace(exists=Mock(return_value=False))

        def get_doc(values):
            created.append(values)
            return types.SimpleNamespace(insert=Mock(return_value=None))

        frappe.get_doc = Mock(side_effect=get_doc)
        with patch.dict(sys.modules, {"frappe": frappe}):
            spec = importlib.util.spec_from_file_location("ss97_specialty_role_migration", SOURCE)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.execute()

        self.assertEqual({item["role_name"] for item in created}, {
            "SS97 Technicien N2", "SS97 Technicien N3", "SS97 Technicien N4",
        })
        self.assertTrue(all(item["desk_access"] == 0 and item["is_custom"] == 1
                            for item in created))
        self.assertTrue(all(set(item) == {"doctype", "role_name", "desk_access", "is_custom"}
                            for item in created))

    def test_never_overwrites_existing_roles(self):
        frappe = types.ModuleType("frappe")
        frappe.db = types.SimpleNamespace(exists=Mock(return_value=True))
        frappe.get_doc = Mock()
        with patch.dict(sys.modules, {"frappe": frappe}):
            spec = importlib.util.spec_from_file_location("ss97_specialty_role_migration_repeat", SOURCE)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.execute()
        frappe.get_doc.assert_not_called()

    def test_post_model_sync_patch_is_registered(self):
        self.assertIn("softsystem97.patches.v1_0.ss97_specialty_roles",
                      PATCHES.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
