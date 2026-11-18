"""Privacy and workflow tests, never reading production identity files."""

import ast
import json
import unittest
from pathlib import Path

from softsystem97.technician_os.documents import (
    MAX_FILE_BYTES, REQUIRED_DOCUMENTS, check_private_upload, safe_private_file_url,
)


ROOT = Path(__file__).resolve().parents[1]


class TechnicianDocumentsTests(unittest.TestCase):
    def setUp(self):
        self.valid = {
            "owner": "candidate@example.test", "is_private": 1,
            "file_url": "/private/files/test-attestation.pdf",
            "file_name": "attestation.pdf", "file_size": 14242,
            "attached_to_doctype": None, "attached_to_name": None,
        }

    def test_expected_credentials_only(self):
        self.assertEqual(set(REQUIRED_DOCUMENTS), {"IDENTITY", "DIPLOMA"})
        self.assertEqual(MAX_FILE_BYTES, 8 * 1024 * 1024)

    def test_private_candidate_file_is_valid(self):
        self.assertTrue(check_private_upload(self.valid, "candidate@example.test"))

    def test_rejects_public_foreign_attached_or_oversized_uploads(self):
        modifications = [
            {"owner": "other@example.test"}, {"is_private": 0},
            {"file_url": "https://others.example.test/file.pdf"},
            {"file_url": "/files/public.pdf"},
            {"file_url": "/private/files/../secret.pdf"},
            {"file_url": "/private/files/%2e%2e%2fsecret.pdf"},
            {"file_url": "/private/files/%252e%252e%252fsecret.pdf"},
            {"file_url": "/private/files/photo.pdf?download=1"},
            {"file_url": "/private/files/subdir/photo.pdf"},
            {"file_name": "payload.exe"}, {"file_name": "photo.pdf.exe"},
            {"file_size": 0}, {"file_size": MAX_FILE_BYTES + 1},
            {"file_size": "unknown"}, {"attached_to_doctype": "Customer"},
            {"attached_to_name": "CUST-001"},
        ]
        for changed in modifications:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                check_private_upload({**self.valid, **changed}, "candidate@example.test")

    def test_safe_private_url_does_not_accept_encoded_path_escape(self):
        self.assertTrue(safe_private_file_url("/private/files/cv%20technicien.pdf"))
        for path in ("/private/files/", "/private/files/%2fetc%2fpasswd",
                     "/private/files/%252e%252e%255csecret.pdf",
                     "/private/files/photo.pdf#private", "/private/files/./photo.pdf"):
            with self.subTest(path=path):
                self.assertFalse(safe_private_file_url(path))

    def test_document_doctype_private_read_only(self):
        path = (ROOT / "softsystem97/softsystem97/doctype/ss97_technician_document"
                / "ss97_technician_document.json")
        schema = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(schema["permissions"], [
            {"role": "System Manager", "read": 1, "report": 1},
        ])
        self.assertEqual(schema["autoname"], "field:document_id")
        self.assertFalse(any(field["fieldname"] in {"rib", "iban", "password"}
                             for field in schema["fields"]))

    def test_server_must_check_ownership_and_documents_before_activation(self):
        source = (ROOT / "softsystem97/technician_os/api.py").read_text(encoding="utf-8")
        names = {node.name for node in ast.parse(source).body
                 if isinstance(node, ast.FunctionDef)}
        self.assertTrue({"submit_private_document", "get_admin_documents",
                         "review_document", "_documents_verified"} <= names)
        self.assertIn("check_private_upload(file_data, user)", source)
        self.assertIn('if not _documents_verified(profile):', source)
        self.assertIn('doc.state != "REJECTED"', source)
        self.assertIn('reviewer == doc.candidate_user', source)
        self.assertNotIn("allow_guest=True", source)
        self.assertNotIn("frappe.sendmail", source)

    def test_catalog_guest_only_for_public_read_endpoint(self):
        source = (ROOT / "softsystem97/cyber_assessment/api.py").read_text(encoding="utf-8")
        self.assertIn('@frappe.whitelist(allow_guest=True, methods=["GET"])\ndef get_catalog()', source)
        self.assertNotIn('allow_guest=True, methods=["POST"]', source)


if __name__ == "__main__":
    unittest.main()
