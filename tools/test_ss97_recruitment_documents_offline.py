"""No real identities are transmitted or stored by these offline tests."""

import base64
import io
import importlib
import sys
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image
from reportlab.pdfgen.canvas import Canvas

from softsystem97.recruitment.validation import (
    TRACKS, TRACK_OPTIONS, check_upload_for_field,
    validate_embedded_uploads, detect_file_type,
)
from softsystem97.technician_os.documents import check_document_content


def pdf(text):
    output = io.BytesIO()
    writer = Canvas(output)
    writer.drawString(30, 750, text)
    writer.showPage()
    writer.save()
    return output.getvalue()


def image(format):
    output = io.BytesIO()
    Image.new("RGB", (40, 40), color=(100, 110, 120)).save(output, format)
    return output.getvalue()


def embedded(content, kind="application/pdf", filename="document.pdf"):
    return filename + ",data:" + kind + ";base64," + base64.b64encode(content).decode("ascii")


class RecruitmentDocumentsTests(unittest.TestCase):
    def test_three_real_paths_and_placeholder(self):
        self.assertEqual(TRACKS, ("N2", "N3", "N4"))
        self.assertEqual(TRACK_OPTIONS, "\nN2\nN3\nN4")

    def test_real_cv_pdf_and_image_are_parsed(self):
        self.assertEqual(check_upload_for_field("cv_file", pdf("CURRICULUM VITAE")), "pdf")
        self.assertEqual(check_upload_for_field("photo_file", image("JPEG")), "jpg")
        self.assertEqual(check_upload_for_field("photo_file", image("PNG")), "png")

    def test_invoice_or_wrong_document_rejected(self):
        with self.assertRaisesRegex(ValueError, "autre rubrique"):
            check_upload_for_field("id_document_file", pdf("CURRICULUM VITAE"))
        with self.assertRaisesRegex(ValueError, "autre rubrique"):
            check_upload_for_field("diploma_file", pdf("FACTURE CLIENT, total TTC"))

    def test_file_mime_magic_not_trusted(self):
        with self.assertRaises(ValueError):
            check_upload_for_field("cv_file", image("PNG"))
        with self.assertRaises(ValueError):
            check_upload_for_field("id_document_file", b"<script>alert(1)</script>")
        with self.assertRaises(ValueError):
            detect_file_type(b"%PDF-1.4 without trailer")

    def test_encoded_upload_and_private_url_reuse(self):
        validate_embedded_uploads({"cv_file": embedded(pdf("CURRICULUM VITAE"), filename="CV.pdf")})
        with self.assertRaises(ValueError):
            validate_embedded_uploads({"id_document_file": "/private/files/someone_else.pdf"})
        with self.assertRaises(ValueError):
            validate_embedded_uploads({"cv_file": "CV.pdf,data:application/pdf;base64,nonsense"})
        with self.assertRaisesRegex(ValueError, "extension"):
            validate_embedded_uploads({"photo_file": embedded(image("PNG"), "image/png", "photo.pdf")})

    def test_job_applicant_file_privacy_enforced_before_insert(self):
        from softsystem97.recruitment.validation import enforce_private_job_applicant_file
        upload = {"attached_to_doctype": "Job Applicant", "is_private": 0}
        applicant_file = MagicMock()
        applicant_file.get.side_effect = upload.get
        enforce_private_job_applicant_file(applicant_file)
        self.assertEqual(applicant_file.is_private, 1)
        other_file = MagicMock()
        other_file.get.return_value = "Issue"
        enforce_private_job_applicant_file(other_file)
        self.assertFalse(other_file.__dict__.get("is_private"))

    def test_private_technician_documents_need_matching_content(self):
        self.assertTrue(check_document_content("DIPLOMA", "certificate.pdf", pdf("Diplome informatique")))
        self.assertTrue(check_document_content("IDENTITY", "scan.png", image("PNG")))
        with self.assertRaisesRegex(ValueError, "autre rubrique"):
            check_document_content("IDENTITY", "cv.pdf", pdf("Curriculum vitae"))
        with self.assertRaisesRegex(ValueError, "format"):
            check_document_content("DIPLOMA", "renamed.jpg", pdf("Diplome"))

    def test_migration_scoped_only_to_ss97_form(self):
        row = MagicMock(fieldname="technician_type", fieldtype="Select", options="", reqd=0)
        form = MagicMock(doc_type="Job Applicant", web_form_fields=[row])
        mock = MagicMock()
        mock.db.exists.return_value = True
        mock.get_doc.return_value = form
        mock.get_all.side_effect = [
            [MagicMock(name="SoftSystem97 - Postuler")],
            [MagicMock(name="Job Applicant-technician_type", options="", fieldtype="Select")],
        ]
        with patch.dict(sys.modules, {"frappe": mock}):
            migration = importlib.import_module("softsystem97.patches.v1_0.ss97_recruitment_tracks")
            migration.execute()
        self.assertEqual(row.options, TRACK_OPTIONS)
        self.assertEqual(row.reqd, 1)
        form.save.assert_called_once_with(ignore_permissions=True)
        mock.db.set_value.assert_called_once()


if __name__ == "__main__":
    unittest.main()
