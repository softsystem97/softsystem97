"""Local operator-tool tests, without production users or credentials."""
import unittest
import frappe
from softsystem97.provisioning import (
    TECHNICIAN_ROLE, plan_existing_user, prepare_technician_role, role_inventory,
)


class TestProvisioning(unittest.TestCase):
    def setUp(self):
        if not frappe.conf.allow_tests or not frappe.local.site.startswith(('audit.', 'test_')):
            raise RuntimeError('Disposable site required')
        frappe.set_user('Administrator')
        self.role = 'SS97 Lab Technician ' + frappe.generate_hash(length=8)

    def tearDown(self):
        frappe.set_user('Administrator')
        frappe.db.rollback()
        if frappe.db.exists('Role', self.role):
            frappe.delete_doc('Role', self.role)
        frappe.db.commit()

    def test_role_simulation_is_default_and_creates_nothing(self):
        before = frappe.db.count('Role')
        result = prepare_technician_role(self.role)
        self.assertFalse(result['changed'])
        self.assertEqual(result['proposed']['desk_access'], 0)
        self.assertEqual(before, frappe.db.count('Role'))
        self.assertEqual(TECHNICIAN_ROLE, 'SS97 Technicien')
        with self.assertRaises(frappe.ValidationError):
            prepare_technician_role(self.role, dry_run=False)

    def test_explicit_role_creation_is_idempotent_and_grants_nothing(self):
        counts = {dt: frappe.db.count(dt) for dt in ['User', 'Has Role', 'DocPerm', 'Custom DocPerm']}
        first = prepare_technician_role(self.role, dry_run=False, policy_confirmed=True)
        self.assertTrue(first['changed'])
        frappe.db.set_value('Role', self.role, {'desk_access': 1, 'disabled': 1})
        second = prepare_technician_role(self.role, dry_run=False, policy_confirmed=True)
        self.assertFalse(second['changed'])
        self.assertEqual(second['existing'].desk_access, 1)
        self.assertEqual(second['existing'].disabled, 1)
        self.assertEqual(frappe.db.count('Role', {'name': self.role}), 1)
        self.assertEqual(counts, {dt: frappe.db.count(dt) for dt in counts})
        self.assertFalse(first['portal_authorization_verified'])

    def test_candidate_and_administrator_roles_cannot_be_selected(self):
        for role in ['Candidat SS97', 'candidat ss97', 'System Manager', 'system manager', 'Guest']:
            with self.subTest(role=role), self.assertRaises(frappe.ValidationError):
                prepare_technician_role(role)
        with self.assertRaises(frappe.ValidationError):
            prepare_technician_role(self.role, dry_run='false', policy_confirmed=True)

    def test_user_plan_is_repeatable_and_never_creates_a_missing_user(self):
        before = frappe.db.get_value('User', 'Administrator', 'last_name')
        a = plan_existing_user('Administrator', 'LAB REVIEW ONLY')
        b = plan_existing_user('Administrator', 'LAB REVIEW ONLY')
        self.assertEqual(a, b)
        self.assertFalse(a['applied'])
        self.assertEqual(frappe.db.get_value('User', 'Administrator', 'last_name'), before)
        count = frappe.db.count('User')
        with self.assertRaises(frappe.DoesNotExistError):
            plan_existing_user('missing-lab-user@example.invalid')
        self.assertEqual(frappe.db.count('User'), count)

    def test_inventory_is_complete_and_tools_are_admin_only(self):
        self.assertEqual(len(role_inventory()), frappe.db.count('Role'))
        frappe.set_user('Guest')
        for func, args in [(role_inventory, ()), (prepare_technician_role, (self.role,)),
                           (plan_existing_user, ('Administrator',))]:
            with self.subTest(function=func.__name__), self.assertRaises(frappe.PermissionError):
                func(*args)
