"""N2 portal authentication checks; no Frappe bench or production writes."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


SOURCE = Path(__file__).resolve().parents[1] / "softsystem97/portal/technician_access.py"


def load_endpoint(user="n2@example.invalid", enabled=1, roles=(), rows=None):
    frappe = types.ModuleType("frappe")
    frappe.session = types.SimpleNamespace(user=user)
    frappe.whitelist = lambda **options: lambda func: func
    frappe.db = types.SimpleNamespace(get_value=Mock(side_effect=lambda _dt, _name, field: {
        "enabled": enabled, "full_name": "Technicien N2"
    }[field]))
    frappe.get_roles = Mock(return_value=list(roles))
    frappe.get_all = Mock(return_value=rows if rows is not None else [
        {"name": "SS97 Technician", "disabled": 0}
    ])
    with patch.dict(sys.modules, {"frappe": frappe}):
        spec = importlib.util.spec_from_file_location("ss97_release_auth", SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module, frappe


def specialty_endpoint(track="L2", state="ACTIVE", engagement="FREELANCE",
                       enabled_flag=True, roles=None):
    from softsystem97.technician_os.rules import TRACKS
    exact_role = TRACKS[track]["role"]
    assigned = roles if roles is not None else ["Website User", exact_role]
    module, frappe = load_endpoint(roles=assigned, rows=[
        {"name": role, "disabled": 0} for role in assigned if role.startswith("SS97 ")
    ])
    frappe.conf = {"ss97_tech_os": {"enabled": enabled_flag}}
    frappe.db.table_exists = Mock(return_value=True)
    original_get = frappe.db.get_value.side_effect

    def get_value(doctype, name, field, **kwargs):
        if doctype == "SS97 Technician Profile":
            return {"track": track, "state": state, "engagement": engagement}
        return original_get(doctype, name, field)

    frappe.db.get_value.side_effect = get_value
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

    def test_active_n2_n3_n4_specialty_roles_are_recognized(self):
        for track in ("L2", "BANK", "CYBER"):
            with self.subTest(track=track):
                module, _ = specialty_endpoint(track=track)
                self.assertTrue(module.my_technician_access()["isTechnician"])

    def test_suspended_and_unsigned_specialists_cannot_enter(self):
        for state, engagement in (("SUSPENDED", "FREELANCE"),
                                  ("CONTRACT_SIGNED", "FREELANCE"),
                                  ("ACTIVE", "EMPLOYEE")):
            with self.subTest(state=state, engagement=engagement):
                module, _ = specialty_endpoint(state=state, engagement=engagement)
                self.assertFalse(module.my_technician_access()["isTechnician"])

    def test_disabled_specialty_feature_fails_closed(self):
        module, _ = specialty_endpoint(enabled_flag=False)
        self.assertFalse(module.my_technician_access()["isTechnician"])

    def test_multiple_specialty_roles_cannot_bypass_exact_track(self):
        module, _ = specialty_endpoint(roles=["SS97 Technicien N2", "SS97 Technicien N3"])
        self.assertFalse(module.my_technician_access()["isTechnician"])

    def test_generic_role_does_not_bypass_suspended_specialist(self):
        module, _ = specialty_endpoint(state="SUSPENDED", roles=[
            "SS97 Technician", "SS97 Technicien N2"
        ])
        self.assertFalse(module.my_technician_access()["isTechnician"])

    def test_wrong_specialty_is_denied(self):
        module, _ = specialty_endpoint(track="L2", roles=["SS97 Technicien N3"])
        self.assertFalse(module.my_technician_access()["isTechnician"])

    def test_missing_profile_table_is_denied(self):
        module, frappe = specialty_endpoint()
        frappe.db.table_exists.return_value = False
        self.assertFalse(module.my_technician_access()["isTechnician"])

    def test_disabled_specialty_role_is_denied(self):
        module, frappe = specialty_endpoint()
        frappe.get_all.return_value = [{"name": "SS97 Technicien N2", "disabled": 1}]
        self.assertFalse(module.my_technician_access()["isTechnician"])

    def test_release_hooks_keep_password_and_contrast_assets(self):
        hooks = (SOURCE.parent.parent / "hooks.py").read_text(encoding="utf-8")
        self.assertIn("/assets/softsystem97/js/password-visibility.js", hooks)
        self.assertIn("/assets/softsystem97/js/technician_session_auth.js", hooks)
        self.assertIn("technician_session_auth.js?v=20261119-tech-pages-5", hooks)
        self.assertIn("technician_language.js?v=20261119-tech-languages-1", hooks)
        self.assertIn("/assets/softsystem97/css/portal-contrast.css", hooks)


if __name__ == "__main__":
    unittest.main(verbosity=2)
