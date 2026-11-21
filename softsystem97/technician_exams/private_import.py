"""Admin-only import of private N4 questions; always inactive and fail-closed."""
import frappe
from .private_import_rules import check_n4_csv

QUESTION = "SS97 Technician Exam Question"

@frappe.whitelist(methods=["POST"])
def import_inactive_n4(file_id, acknowledgement):
    manager = frappe.session.user
    if (not manager or manager == "Guest"
            or not frappe.db.get_value("User", manager, "enabled")
            or "System Manager" not in frappe.get_roles(manager)):
        frappe.throw("Responsable habilité requis.", frappe.PermissionError)
    if acknowledgement != "IMPORTER_40_INACTIVES":
        frappe.throw("Confirmation manquante.", frappe.PermissionError)
    if not frappe.db.table_exists(QUESTION):
        frappe.throw("Migration des examens manquante.", frappe.PermissionError)
    if not isinstance(file_id, str) or not 1 <= len(file_id) <= 140:
        frappe.throw("Fichier invalide.", frappe.PermissionError)
    meta = frappe.db.get_value("File", file_id,
        ["owner", "is_private", "file_url", "file_name", "file_size",
         "attached_to_doctype", "attached_to_name"], as_dict=True)
    if (not meta or meta.owner != manager or int(meta.is_private or 0) != 1
            or not str(meta.file_url or "").startswith("/private/files/")
            or not str(meta.file_name or "").lower().endswith(".csv")
            or meta.attached_to_doctype or meta.attached_to_name
            or int(meta.file_size or 0) > 200000):
        frappe.throw("Fichier non privé ou non autorisé.", frappe.PermissionError)
    raw = frappe.get_doc("File", file_id).get_content()
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    try:
        batch = check_n4_csv(raw)
    except ValueError as exc:
        frappe.throw(str(exc), frappe.ValidationError)

    # One consistent transaction. Serialize simultaneous admin imports.
    frappe.db.sql("SELECT name FROM tabDocType WHERE name=%s FOR UPDATE", (QUESTION,))
    if frappe.db.count(QUESTION, {"track": "CYBER"}):
        frappe.throw("La banque N4 n'est pas vide. Import refusé.", frappe.PermissionError)
    for record in batch["questions"]:
        doc = frappe.get_doc({"doctype": QUESTION, **record})
        doc.is_active = 0  # Override DocType default=1. No questions go live.
        doc.insert(ignore_permissions=True)
    # No explicit commit: Frappe rolls the request back on any failure.
    return {"imported_count": 40, "active_count": 0,
            "sha256": batch["sha256"],
            "state": "PENDING_HUMAN_REVIEW"}
