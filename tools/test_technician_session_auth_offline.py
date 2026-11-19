"""Safe session-bound technician access tests; no production server needed."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


SOURCE = Path(__file__).resolve().parents[1] / 'softsystem97/portal/technician_access.py'


def module_with_user(user='n2@example.invalid', *, enabled=1, roles=(), rows=None):
    frappe = types.ModuleType('frappe')
    frappe.session = types.SimpleNamespace(user=user)
    frappe.whitelist = lambda **kwargs: lambda func: func
    frappe.db = types.SimpleNamespace(get_value=Mock(side_effect=lambda dt, name, field: {
        'enabled': enabled, 'full_name': 'N2 Example'
    }[field]))
    frappe.get_roles = Mock(return_value=list(roles))
    frappe.get_all = Mock(return_value=rows if rows is not None else [
        {'name': 'SS97 Technician', 'disabled': 0}
    ])
    with patch.dict(sys.modules, {'frappe': frappe}):
        spec = importlib.util.spec_from_file_location('ss97_tech_access_test', SOURCE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod, frappe


class TechnicianSessionAuthTests(unittest.TestCase):
    def test_active_n2_with_canonical_role_is_accepted_without_application_link(self):
        mod, frappe = module_with_user(roles=['SS97 Technician'])
        profile = mod.my_technician_access()
        self.assertTrue(profile['authenticated'])
        self.assertTrue(profile['isTechnician'])
        self.assertFalse(profile['isAdmin'])
        self.assertEqual(profile['fullName'], 'N2 Example')
        frappe.get_all.assert_called_once()
        self.assertEqual(frappe.get_all.call_args.kwargs['fields'], ['name', 'disabled'])

    def test_unrelated_signed_in_user_is_not_technician(self):
        mod, frappe = module_with_user(roles=['Website User'])
        profile = mod.my_technician_access()
        self.assertTrue(profile['authenticated'])
        self.assertFalse(profile['isTechnician'])
        frappe.get_all.assert_not_called()

    def test_french_bridge_role_alone_does_not_grant_historical_access(self):
        mod, _ = module_with_user(roles=['SS97 Technicien'])
        self.assertFalse(mod.my_technician_access()['isTechnician'])

    def test_disabled_role_denied(self):
        mod, _ = module_with_user(roles=['SS97 Technician'], rows=[
            {'name': 'SS97 Technician', 'disabled': 1}
        ])
        self.assertFalse(mod.my_technician_access()['isTechnician'])

    def test_deleted_role_denied(self):
        mod, _ = module_with_user(roles=['SS97 Technician'], rows=[])
        self.assertFalse(mod.my_technician_access()['isTechnician'])

    def test_disabled_user_denied_without_role_lookup(self):
        mod, frappe = module_with_user(enabled=0, roles=['SS97 Technician'])
        self.assertFalse(mod.my_technician_access()['authenticated'])
        frappe.get_roles.assert_not_called()

    def test_guest_denied_without_read(self):
        mod, frappe = module_with_user(user='Guest', roles=['SS97 Technician'])
        self.assertFalse(mod.my_technician_access()['authenticated'])
        frappe.db.get_value.assert_not_called()

    def test_admin_status_preserved_without_technician_grant(self):
        mod, _ = module_with_user(roles=['System Manager'])
        profile = mod.my_technician_access()
        self.assertTrue(profile['isAdmin'])
        self.assertFalse(profile['isTechnician'])

    def test_no_arbitrary_target_user_argument(self):
        mod, _ = module_with_user(roles=['SS97 Technician'])
        with self.assertRaises(TypeError):
            mod.my_technician_access('someone-else@example.invalid')


if __name__ == '__main__':
    unittest.main(verbosity=2)
