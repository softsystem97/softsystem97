"""Repair the empty technician-track selector on the live SS97 Job Applicant Web Form.

The migration changes only the SS97 recruitment form and its backing custom
field. It never creates applicants, grants roles, or approves documents.
"""

import frappe

from softsystem97.recruitment.validation import TRACK_OPTIONS


def execute():
    # Preserve all other Web Forms and their operator-specific configurations.
    forms = frappe.get_all("Web Form", filters={"route": "ss97-job-apply"},
                           fields=["name"], limit_page_length=2)
    if len(forms) == 1:
        web_form = frappe.get_doc("Web Form", forms[0].name)
        if web_form.doc_type == "Job Applicant":
            changed = False
            for row in web_form.web_form_fields:
                if row.fieldname == "technician_type" and row.fieldtype == "Select":
                    if row.options != TRACK_OPTIONS:
                        row.options = TRACK_OPTIONS
                        changed = True
                    if not row.reqd:
                        row.reqd = 1
                        changed = True
            if changed:
                web_form.save(ignore_permissions=True)

    # An empty Custom Field.options also causes Frappe form rendering to fall
    # back to an empty select. Correct the metadata, not merely DOM content.
    for row in frappe.get_all(
        "Custom Field", filters={"dt": "Job Applicant", "fieldname": "technician_type"},
        fields=["name", "options", "fieldtype"], limit_page_length=10,
    ):
        if row.fieldtype == "Select" and row.options != TRACK_OPTIONS:
            frappe.db.set_value("Custom Field", row.name, "options", TRACK_OPTIONS)

    frappe.clear_cache(doctype="Job Applicant")
    frappe.clear_cache(doctype="Web Form")
