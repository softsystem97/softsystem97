"""Response validation only: no API credentials or network operations."""
import importlib.util
from pathlib import Path
import unittest


class TestRestResponse(unittest.TestCase):
    def test_authentication_requires_a_nonempty_identity_object(self):
        path = Path(__file__).resolve().parents[2] / 'tools' / 'check_rest_auth.py'
        spec = importlib.util.spec_from_file_location('ss97_check_rest_auth', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for payload in [None, [], ['Administrator'], 'Administrator', {},
                        {'message': ''}, {'message': ' '}, {'message': 'Guest'},
                        {'message': ' Guest '}, {'message': None}, {'message': 1}]:
            with self.subTest(payload=payload):
                self.assertFalse(module.is_authenticated_payload(payload))
        self.assertTrue(module.is_authenticated_payload({'message': 'Administrator'}))
        self.assertTrue(module.is_authenticated_payload({'message': 'lab-user@example.invalid'}))
