"""Explicit seed of fictional development companies. Never runs on real sites."""

import frappe

from . import api


def seed():
    frappe.only_for("System Manager")
    if not frappe.conf.allow_tests or not frappe.local.site.startswith(
        ("audit.", "test_")
    ):
        frappe.throw("Disposable laboratory site required", frappe.PermissionError)
    suffix = frappe.generate_hash(length=6)
    customers = []
    for label in ("A", "B"):
        customer = frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": f"SS97 Cyber DEMO {label} {suffix}",
                "customer_type": "Company",
            }
        ).insert()
        customers.append(customer.name)
        frappe.get_doc(
            {
                "doctype": "SS97 Cyber Company",
                "customer": customer.name,
                "authorization_status": "Pending",
            }
        ).insert()
        asset = api.create_record(
            "asset",
            {
                "customer": customer.name,
                "asset_name": f"DEMO server {label}",
                "asset_type": "Server",
                "operating_system": "Synthetic OS",
                "maintenance_state": "Due",
            },
        )
        audit = api.create_record(
            "audit",
            {
                "customer": customer.name,
                "title": "DEMO baseline review",
                "asset": asset["name"],
                "status": "Completed",
                "checks": [
                    {
                        "question": "Are backups restore-tested?",
                        "result": "Fail",
                        "observation": "Synthetic missing proof",
                    },
                    {"question": "Is MFA enabled?", "result": "Pass"},
                ],
            },
        )
        api.create_record(
            "risk",
            {
                "customer": customer.name,
                "title": "DEMO backup verification missing",
                "asset": asset["name"],
                "audit": audit["name"],
                "severity": "High",
            },
        )
        api.create_record(
            "incident",
            {
                "customer": customer.name,
                "title": "DEMO suspicious activity",
                "severity": "Critical",
                "description": "Fictional demonstration; no live detection.",
            },
        )
    return {
        "customers": customers,
        "dashboard": "/ss97-cyber",
        "external_connections": False,
    }
