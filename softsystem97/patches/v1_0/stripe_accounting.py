"""Add accounting relations only. No keys, accounts, roles, users or activation."""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    fields = {
        "Sales Invoice": [
            ("ss97_linked_issue", "Link", "Issue"),
            ("ss97_stripe_session_id", "Data", None),
            ("ss97_stripe_payment_intent", "Data", None),
            ("ss97_stripe_invoice_id", "Data", None),
            ("ss97_stripe_checkout_url", "Small Text", None),
            ("ss97_stripe_mode", "Select", "test\nlive"),
            ("ss97_payment_status", "Select", "\npending\npaid\nfailed\nrefunded\nrefund_pending_review\ndisputed"),
            ("ss97_receipt_ref", "Data", None),
            ("ss97_paid_on", "Datetime", None),
        ],
        "Payment Entry": [("ss97_stripe_transaction_id", "Data", None)],
        "Customer": [
            ("ss97_stripe_customer_id", "Data", None),
            ("ss97_stripe_subscription_id", "Data", None),
            ("ss97_stripe_subscription_status", "Data", None),
            ("ss97_stripe_subscription_event_created", "Int", None),
        ],
    }
    additions = {}
    for doctype, rows in fields.items():
        meta = frappe.get_meta(doctype)
        for name, kind, options in rows:
            old = meta.get_field(name)
            if old:
                # Preserve existing fields and their business-specific options.
                if name == "ss97_payment_status" and old.fieldtype == "Select":
                    values = (old.options or "").splitlines()
                    values.extend(x for x in options.splitlines() if x not in values)
                    frappe.make_property_setter({"doctype": doctype, "fieldname": name,
                        "property": "options", "value": "\n".join(values), "property_type": "Text"})
                continue
            additions.setdefault(doctype, []).append(dict(fieldname=name, label=name,
                fieldtype=kind, options=options, read_only=1, no_copy=1,
                unique=1 if name == "ss97_stripe_transaction_id" else 0))
    create_custom_fields(additions, update=False)
    # Enforce the deduplication constraint even when the field predates this patch.
    frappe.db.add_unique("Payment Entry", ["ss97_stripe_transaction_id"], "ss97_stripe_transaction_unique")
