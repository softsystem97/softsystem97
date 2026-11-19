"""Fail-closed server checks for the public technician job application.

Technical file recognition is NOT an authenticity or identity verification.
Independent document review is handled by SS97 Technician Document.
"""

import base64
import binascii
import json
import io
import re
import unicodedata


TRACKS = ("N2", "N3", "N4")
TRACK_OPTIONS = "\n".join(("", *TRACKS))
MAX_ENCODED_FILE = 12 * 1024 * 1024
FILE_RULES = {
    "cv_file": ("CV", frozenset({"pdf"})),
    "cover_letter_file": ("Lettre de motivation", frozenset({"pdf"})),
    "photo_file": ("Photo", frozenset({"jpg", "png"})),
    "diploma_file": ("Diplôme", frozenset({"pdf", "jpg", "png"})),
    "id_document_file": ("Pièce d'identité", frozenset({"pdf", "jpg", "png"})),
}


def detect_file_type(contents):
    """Identify real bytes, never trust filename, extension, or browser MIME."""
    if not isinstance(contents, bytes) or not contents:
        raise ValueError("Le fichier est vide ou illisible.")
    if contents.startswith(b"%PDF-") and b"%%EOF" in contents[-1024:]:
        return "pdf"
    if contents.startswith(b"\xff\xd8\xff") and contents.rstrip().endswith(b"\xff\xd9"):
        return "jpg"
    if contents.startswith(b"\x89PNG\r\n\x1a\n") and b"IEND" in contents[-32:]:
        return "png"
    raise ValueError("Document non reconnu : PDF, JPEG ou PNG valide requis.")


def inspect_document_bytes(contents):
    """Parse local bytes and return (format, textual_class).

    Scanned PDFs and photos have no dependable local OCR: their class is
    'unknown' and a human must inspect them before any activation. No content
    is forwarded to an external AI, written to logs, or returned to clients.
    """
    actual = detect_file_type(contents)
    if actual in {"jpg", "png"}:
        from PIL import Image, UnidentifiedImageError

        try:
            with Image.open(io.BytesIO(contents)) as im:
                if im.width * im.height > 25_000_000:
                    raise ValueError("Image trop grande.")
                expected = "JPEG" if actual == "jpg" else "PNG"
                if im.format != expected:
                    raise ValueError("Format d'image incohérent.")
                im.verify()
        except (OSError, UnidentifiedImageError) as exc:
            raise ValueError("Image corrompue ou illisible.") from exc
        return actual, "unknown"

    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(contents), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 30:
            raise ValueError("PDF protégé ou nombre de pages non autorisé.")
        visible = " ".join((page.extract_text() or "") for page in reader.pages[:3])[:12000]
    except (ValueError, ImportError):
        raise
    except Exception as exc:
        raise ValueError("PDF illisible ou endommagé.") from exc

    visible = unicodedata.normalize("NFKD", visible).encode("ascii", "ignore").decode().lower()
    visible = re.sub(r"\s+", " ", visible)
    if re.search(r"\b(curriculum vitae|experiences professionnelles|professional experience)\b", visible):
        return actual, "cv"
    if re.search(r"\b(carte nationale d.identite|national identity card|passport|passeport|titre de sejour)\b", visible):
        return actual, "identity"
    if re.search(r"\b(diplome|certificat de formation|certificate of completion|degree certificate|attestation de formation)\b", visible):
        return actual, "diploma"
    if re.search(r"\b(invoice number|facture n[°o]|facture client|total ttc)\b", visible):
        return actual, "invoice"
    return actual, "unknown"


def check_upload_for_field(fieldname, contents):
    label, allowed = FILE_RULES[fieldname]
    if not 0 < len(contents) <= 8 * 1024 * 1024:
        raise ValueError(f"{label} : fichier vide ou supérieur à 8 Mo.")
    actual, category = inspect_document_bytes(contents)
    if actual not in allowed:
        raise ValueError(f"{label} : format incorrect pour cette rubrique.")
    expected = {"cv_file": "cv", "diploma_file": "diploma",
                "id_document_file": "identity"}.get(fieldname)
    if category == "invoice" or (expected and category not in {expected, "unknown"}):
        raise ValueError(f"{label} : le document semble appartenir à une autre rubrique.")
    return actual


def validate_embedded_uploads(form_data):
    """Inspect raw web-form base64 attachments before Frappe saves the applicant.

    Values already stored as Frappe File URLs are not attested here; those
    require an independent private-file review before technician activation.
    """
    if not isinstance(form_data, dict):
        raise ValueError("Données de candidature invalides.")
    for fieldname, (label, _) in FILE_RULES.items():
        value = form_data.get(fieldname)
        if not value:
            continue
        if not isinstance(value, str):
            raise ValueError(f"{label} : document invalide.")
        if ",data:" in value:
            # Frappe Web Form accepts "filename,data:<MIME>;base64,<bytes>".
            # The comma preceding the data URL separates its actual filename.
            filename, dataurl = value.split(",", 1)
            if (not filename or len(filename) > 180
                    or "/" in filename or "\\" in filename
                    or not dataurl.startswith("data:") or ";base64," not in dataurl):
                raise ValueError(f"{label} : encodage non reconnu.")
            encoded = dataurl.partition(";base64,")[2]
            if not 0 < len(encoded) <= MAX_ENCODED_FILE:
                raise ValueError(f"{label} : document trop volumineux.")
            try:
                contents = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ValueError(f"{label} : document corrompu.") from exc
            actual = check_upload_for_field(fieldname, contents)
            suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            expected_extension = {"jpeg": "jpg"}.get(suffix, suffix)
            if expected_extension != actual:
                raise ValueError(f"{label} : l'extension ne correspond pas au fichier.")
        else:
            # Existing File URLs cannot be safely attributed to an anonymous
            # new applicant. Do not let guests reuse somebody else's File.
            raise ValueError(f"{label} : importez le fichier directement dans le formulaire.")


def enforce_private_job_applicant_file(doc, method=None):
    """Keep new Job Applicant uploads private at creation, before storage path is set.

    Frappe's Web Form `accept` creates File documents without an explicit
    privacy bit; the absence must never make identity files world-readable.
    Do not retroactively flip existing public flags without moving the blob.
    """
    if doc.get("attached_to_doctype") == "Job Applicant":
        doc.is_private = 1


def validate_technician_application(doc, method=None):
    """Called via doc_events; applies only to the SS97 recruitment Web Form."""
    import frappe

    if not getattr(frappe.flags, "in_web_form", False):
        return
    form_name = frappe.form_dict.get("web_form")
    if (not form_name or
            frappe.db.get_value("Web Form", form_name, "route") != "ss97-job-apply"):
        return
    if doc.get("technician_type") not in TRACKS:
        frappe.throw("Choisissez un parcours : N2, N3 ou N4.")
    try:
        payload = frappe.form_dict.get("data")
        if not isinstance(payload, dict):
            payload = json.loads(payload or "{}")
        validate_embedded_uploads(payload)
    except (ValueError, TypeError) as exc:
        frappe.throw(str(exc))
