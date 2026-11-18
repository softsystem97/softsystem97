"""Customer-facing mission follow-up; authorization lives in the API."""

import frappe


def get_context(context):
    context.no_cache = 1
    context.is_guest = frappe.session.user == "Guest"
    context.title = "Soft System 97 — Suivi de mon intervention"
