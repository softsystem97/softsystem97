"""Offline checks: no live exams, tokens, profiles or Frappe server touched."""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'softsystem97/portal/technician_exam_entry.py'
JAVASCRIPT = ROOT / 'softsystem97/public/js/technician_exam_entry.js'


class StubDatabase:
    def __init__(self):
        self.enabled = True
        self.rows = []
        self.filters = None

    def get_value(self, doctype, name, field):
        assert (doctype, field) == ('User', 'enabled')
        return self.enabled

    def table_exists(self, doctype):
        return doctype == 'SS97 Technician Application'


class LegacyExamEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = StubDatabase()
        cls.session = SimpleNamespace(user='cybermoses1@gmail.com')
        cls.roles = ['Website User', 'SS97 Technician', 'SS97 Technicien N2']

        def get_all(doctype, filters, fields, limit_page_length):
            assert doctype == 'SS97 Technician Application'
            assert limit_page_length == 2
            cls.database.filters = filters
            return cls.database.rows

        fake_frappe = SimpleNamespace(
            session=cls.session, db=cls.database,
            PermissionError=PermissionError,
            whitelist=lambda **kwargs: lambda fn: fn,
            throw=lambda message, error: (_ for _ in ()).throw(error(message)),
            get_all=get_all,
            get_roles=lambda user: cls.roles if user == cls.session.user else [],
        )
        original = sys.modules.get('frappe')
        sys.modules['frappe'] = fake_frappe
        try:
            spec = importlib.util.spec_from_file_location('ss97_legacy_exam_entry', SOURCE)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.module = module
        finally:
            if original is None:
                sys.modules.pop('frappe', None)
            else:
                sys.modules['frappe'] = original

    def setUp(self):
        self.session.user = 'cybermoses1@gmail.com'
        self.database.enabled = True
        self.database.rows = [{
            'name': 'SS97-TECH-00283',
            'email_id': 'cybermoses1@gmail.com',
            'recruitment_status': 'Examen technique',
            'exam_access_token': 'mockTestToken123456',
        }]
        self.database.filters = None

    def test_returns_only_own_preissued_invitation(self):
        result = self.module.get_my_exam_entry()
        self.assertEqual(self.database.filters, {'portal_user': self.session.user})
        target = urlsplit(result['url'])
        self.assertEqual(target.path, '/examen-technicien')
        self.assertEqual(parse_qs(target.query), {
            'app': ['SS97-TECH-00283'], 'token': ['mockTestToken123456'],
        })
        self.assertNotIn('score', result)
        self.assertNotIn('started', result)

    def test_guests_disabled_users_and_unlinked_profiles_are_denied(self):
        self.session.user = 'Guest'
        with self.assertRaises(PermissionError):
            self.module.get_my_exam_entry()
        self.session.user = 'cybermoses1@gmail.com'
        self.database.enabled = False
        with self.assertRaises(PermissionError):
            self.module.get_my_exam_entry()
        self.database.enabled = True
        self.database.rows = []
        with self.assertRaises(PermissionError):
            self.module.get_my_exam_entry()

    def test_duplicate_or_cross_account_application_denied(self):
        self.database.rows[0]['email_id'] = 'someoneelse@example.com'
        with self.assertRaises(PermissionError):
            self.module.get_my_exam_entry()
        self.database.rows[0]['email_id'] = self.session.user
        self.database.rows.append(dict(self.database.rows[0]))
        with self.assertRaises(PermissionError):
            self.module.get_my_exam_entry()

    def test_unissued_invalid_or_closed_exam_denied(self):
        row = self.database.rows[0]
        for value in (None, '', '../unsafe', 'a' * 129):
            row['exam_access_token'] = value
            with self.subTest(token=value), self.assertRaises(PermissionError):
                self.module.get_my_exam_entry()
        row['exam_access_token'] = 'mockTestToken123456'
        row['recruitment_status'] = 'Technicien actif'
        with self.assertRaises(PermissionError):
            self.module.get_my_exam_entry()

    def test_role_compatibility_uses_current_session_only(self):
        self.assertEqual(self.module.get_my_portal_roles(), ['SS97 Technician'])
        with self.assertRaises(TypeError):
            self.module.get_my_portal_roles('another@example.com')

    def test_script_is_syntax_valid_and_cannot_start_or_grade_exams(self):
        import subprocess
        subprocess.run(['node', '--check', str(JAVASCRIPT)], check=True, capture_output=True)
        source = JAVASCRIPT.read_text(encoding='utf-8')
        self.assertIn('get_my_exam_entry', source)
        self.assertIn('get_my_portal_roles', source)
        self.assertNotIn('submit_exam', source)
        self.assertNotIn('start_exam', source)
        self.assertNotIn('correct_option', source)


if __name__ == '__main__':
    unittest.main()
