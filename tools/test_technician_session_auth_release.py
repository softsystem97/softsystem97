"""N2 portal authentication checks; no Frappe bench or production writes."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


SOURCE = Path(__file__).resolve().parents[1] / "softsystem97/portal/technician_access.py"


def load_endpoint(user="n2@example.invalid", enabled=1, roles=(), rows=None, profile=None):
    frappe = types.ModuleType("frappe")
    frappe.session = types.SimpleNamespace(user=user)
    frappe.whitelist = lambda **options: lambda func: func
    def db_value(doctype, _name, field, **_options):
        if doctype == "SS97 Technician Profile":
            return profile
        return {"enabled": enabled, "full_name": "Technicien N2"}[field]

    frappe.db = types.SimpleNamespace(
        get_value=Mock(side_effect=db_value),
        table_exists=Mock(return_value=True),
    )
    frappe.get_roles = Mock(return_value=list(roles))
    frappe.get_all = Mock(return_value=rows if rows is not None else [
        {"name": "SS97 Technician", "disabled": 0}
    ])
    with patch.dict(sys.modules, {"frappe": frappe}):
        spec = importlib.util.spec_from_file_location("ss97_release_auth", SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module, frappe


class N2SessionReleaseTests(unittest.TestCase):
    def test_valid_n2_website_user_does_not_need_application_list_permission(self):
        module, frappe = load_endpoint(roles=["Website User", "SS97 Technician"])
        result = module.my_technician_access()
        self.assertTrue(result["authenticated"])
        self.assertTrue(result["isTechnician"])
        self.assertFalse(result["isAdmin"])
        frappe.get_all.assert_called_once()
        self.assertEqual(frappe.get_all.call_args.kwargs["fields"], ["name", "disabled"])

    def test_unrelated_account_does_not_gain_access(self):
        module, frappe = load_endpoint(roles=["Website User"])
        result = module.my_technician_access()
        self.assertTrue(result["authenticated"])
        self.assertFalse(result["isTechnician"])
        frappe.get_all.assert_not_called()

    def test_validated_n2_specialist_can_access_portal_after_graduation(self):
        module, _ = load_endpoint(
            roles=["Website User", "SS97 Technicien N2"],
            rows=[{"name": "SS97 Technicien N2", "disabled": 0}],
            profile={"track": "L2", "state": "ACTIVE", "engagement": "FREELANCE"},
        )
        self.assertTrue(module.my_technician_access()["isTechnician"])

    def test_role_alone_cannot_bypass_graduation(self):
        module, _ = load_endpoint(
            roles=["SS97 Technicien N2"],
            rows=[{"name": "SS97 Technicien N2", "disabled": 0}],
        )
        self.assertFalse(module.my_technician_access()["isTechnician"])

    def test_suspended_graduate_is_denied(self):
        module, _ = load_endpoint(
            roles=["SS97 Technicien N2"],
            rows=[{"name": "SS97 Technicien N2", "disabled": 0}],
            profile={"track": "L2", "state": "SUSPENDED", "engagement": "FREELANCE"},
        )
        self.assertFalse(module.my_technician_access()["isTechnician"])

    def test_suspended_specialist_cannot_fall_back_to_generic_role(self):
        module, _ = load_endpoint(
            roles=["SS97 Technician", "SS97 Technicien N2"],
            rows=[
                {"name": "SS97 Technician", "disabled": 0},
                {"name": "SS97 Technicien N2", "disabled": 0},
            ],
            profile={"track": "L2", "state": "SUSPENDED", "engagement": "FREELANCE"},
        )
        self.assertFalse(module.my_technician_access()["isTechnician"])

    def test_mismatched_track_does_not_grant_portal_access(self):
        module, _ = load_endpoint(
            roles=["SS97 Technicien N2"],
            rows=[{"name": "SS97 Technicien N2", "disabled": 0}],
            profile={"track": "BANK", "state": "ACTIVE", "engagement": "FREELANCE"},
        )
        self.assertFalse(module.my_technician_access()["isTechnician"])

    def test_multiple_specialities_do_not_bypass_role_integrity(self):
        roles = ["SS97 Technicien N2", "SS97 Technicien N3"]
        module, _ = load_endpoint(
            roles=roles,
            rows=[{"name": role, "disabled": 0} for role in roles],
            profile={"track": "L2", "state": "ACTIVE", "engagement": "FREELANCE"},
        )
        self.assertFalse(module.my_technician_access()["isTechnician"])

    def test_unrecognised_role_does_not_bypass_gate(self):
        module, _ = load_endpoint(roles=["SS97 Technicien"])
        self.assertFalse(module.my_technician_access()["isTechnician"])

    def test_disabled_role_denied(self):
        module, _ = load_endpoint(roles=["SS97 Technician"], rows=[
            {"name": "SS97 Technician", "disabled": 1}
        ])
        self.assertFalse(module.my_technician_access()["isTechnician"])

    def test_deleted_role_denied(self):
        module, _ = load_endpoint(roles=["SS97 Technician"], rows=[])
        self.assertFalse(module.my_technician_access()["isTechnician"])

    def test_disabled_account_denied_before_role_lookup(self):
        module, frappe = load_endpoint(enabled=0, roles=["SS97 Technician"])
        self.assertFalse(module.my_technician_access()["authenticated"])
        frappe.get_roles.assert_not_called()

    def test_guest_denied_before_any_lookup(self):
        module, frappe = load_endpoint(user="Guest", roles=["SS97 Technician"])
        self.assertFalse(module.my_technician_access()["authenticated"])
        frappe.db.get_value.assert_not_called()

    def test_admin_only_is_not_automatically_a_technician(self):
        module, _ = load_endpoint(roles=["System Manager"])
        status = module.my_technician_access()
        self.assertTrue(status["isAdmin"])
        self.assertFalse(status["isTechnician"])

    def test_cannot_lookup_another_user_via_user_argument(self):
        module, _ = load_endpoint(roles=["SS97 Technician"])
        with self.assertRaises(TypeError):
            module.my_technician_access("someone@example.invalid")

    def test_release_hooks_keep_password_and_contrast_assets(self):
        hooks = (SOURCE.parent.parent / "hooks.py").read_text(encoding="utf-8")
        self.assertIn("/assets/softsystem97/js/password-visibility.js", hooks)
        self.assertIn("/assets/softsystem97/js/technician_session_auth.js", hooks)
        self.assertIn("/assets/softsystem97/css/portal-contrast.css", hooks)


if __name__ == "__main__":
    unittest.main(verbosity=2)
