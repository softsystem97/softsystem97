import frappe

from softsystem97.cyber.reports import detail

no_cache = 1


def get_context(context):
    context.no_cache = 1
    context.report = frappe._dict(detail(frappe.form_dict.get("name")))
    context.report.data = frappe._dict(context.report.data)
