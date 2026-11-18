import frappe


def get_context(context):
    context.no_cache = 1
    context.is_guest = frappe.session.user == "Guest"
    context.title = "SS97 TECH OS — Espace technicien"
