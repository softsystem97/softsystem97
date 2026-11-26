import frappe
from frappe.model.document import Document


class SS97RemoteSession(Document):
    def validate(self):
        # Only remote.api may change session state. No direct client DocPerm.
        if not self.ticket_name or not self.customer or not self.technician:
            frappe.throw("Une session doit être liée à un ticket, un client et un technicien.")
