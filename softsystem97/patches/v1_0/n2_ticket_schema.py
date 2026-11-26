"""Migration idempotente du schema N2."""

import frappe


def execute():

    doctype = "Issue"
    fieldname = "ss97_technician"

    meta = frappe.get_meta(doctype)

    field = meta.get_field(fieldname)

    if field:

        if field.fieldtype != "Link" or field.options != "User":

            frappe.throw(
                "Champ technicien incompatible : "
                "migration manuelle requise."
            )

        return {"state": "existing"}

    frappe.get_doc({
        "doctype": "Custom Field",
        "dt": doctype,
        "fieldname": fieldname,
        "label": "Technicien SS97",
        "fieldtype": "Link",
        "options": "User",
        "insert_after": "customer",
        "read_only": 1
    }).insert()

    frappe.clear_cache(doctype=doctype)

    field = frappe.get_meta(doctype).get_field(fieldname)

    if not field or field.options != "User":
        frappe.throw("Migration N2 non confirmee.")

    return {"state": "created"}
