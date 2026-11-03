"""Reviewed, opt-in adapters for the actual production Server Scripts/Web Page.

No private script is exported. Native save/version hooks preserve an audit trail.
This installer never activates payments, provisions users, or handles secrets.
"""
from pathlib import Path


REQUEST_PAYMENT_SCRIPT = '''# SS97 secure invoice Checkout adapter v1
frappe.call("softsystem97.integrations.historical_ticket_guard.require_write_session")
ticket = frappe.form_dict.get("ticket") or frappe.form_dict.get("issue") or frappe.form_dict.get("name") or ""
if not isinstance(ticket, str) or not ticket:
    frappe.throw("Référence ticket requise.", frappe.ValidationError)
result = frappe.call("softsystem97.integrations.stripe.checkout.create_ticket_checkout", issue=ticket)
frappe.response["message"] = {"ok": True, "ticket": ticket, "invoice": result["invoice"],
    "checkout_url": result["checkout_url"], "session_id": result["session_id"]}
'''

CONFIRM_PAYMENT_SCRIPT = '''# SS97 read-only accounting confirmation adapter v1
frappe.call("softsystem97.integrations.historical_ticket_guard.require_write_session")
ticket = frappe.form_dict.get("ticket") or frappe.form_dict.get("issue") or frappe.form_dict.get("name") or ""
if not isinstance(ticket, str) or not ticket:
    frappe.throw("Référence ticket requise.", frappe.ValidationError)
result = frappe.call("softsystem97.integrations.stripe.checkout.get_ticket_payment_status", issue=ticket)
confirmed = result.get("ok") is True
frappe.response["message"] = {"ok": confirmed, "ticket": ticket,
    "message": "Paiement confirmé" if confirmed else "Paiement en cours de vérification."}
'''

PATCH_BODY = '''
if frappe.session.user != "Administrator" and not frappe.db.exists("Has Role", {
    "parent":frappe.session.user,"parenttype":"User","role":"System Manager"}):
    frappe.throw("Administration requise.", frappe.PermissionError)
changes = []
pending = []
for item in adapters:
    doc = frappe.get_doc("Server Script", item["name"])
    if doc.script_type != "API" or doc.api_method != item["method"] or doc.disabled:
        frappe.throw("API de paiement différente : revue manuelle requise.")
    current = doc.script or ""
    if current != item["source"]:
        if item["expected"] not in current:
            frappe.throw("Code de paiement différent : revue manuelle requise.")
        doc.script = item["source"]
        doc.allow_guest = 0
        pending.append(doc)
        changes.append({"doctype":"Server Script","name":doc.name,"field":"script"})
pages = frappe.get_all("Web Page", filters={"route":"espace-client/ticket"}, pluck="name", limit_page_length=2)
if len(pages) != 1:
    frappe.throw("Une page client existante unique est requise.")
page = frappe.get_doc("Web Page", pages[0])
current = page.javascript or ""
marker = "/* SS97_SECURE_TICKET_PAYMENT_V1 */"
if marker not in current:
    if "function ss97Call(" not in current or "function load()" not in current:
        frappe.throw("Page client différente : revue manuelle requise.")
    html = page.main_section or ""
    if 'id="ticket"' not in html and "id='ticket'" not in html:
        frappe.throw("Point de montage client introuvable.")
    page.javascript = current + "\\n" + addon
    pending.append(page)
    changes.append({"doctype":"Web Page","name":page.name,"field":"javascript"})
if not dry_run:
    for doc in pending:
        doc.save()
print({"dry_run":dry_run,"changes":changes,"payment_activation":False,"accounting_entries_created":False})
'''


def console_script(*, dry_run=True):
    """Same reviewed code for the supported Cloud System Console (no imports)."""
    if type(dry_run) is not bool:
        raise ValueError("dry_run must be a boolean")
    adapters = [
        {"name": "SS97 Ticket Request Payment", "method": "ss97_ticket_request_payment",
         "expected": "Session de paiement existante (grille SoftSystem97).", "source": REQUEST_PAYMENT_SCRIPT},
        {"name": "SS97 Ticket Confirm Payment", "method": "ss97_ticket_confirm_payment",
         "expected": 'issue.db_set("ss97_payment_status", "paid"', "source": CONFIRM_PAYMENT_SCRIPT},
    ]
    addon = Path(__file__).with_name("ticket_payment.js").read_text()
    return f"dry_run = {dry_run!r}\nadapters = {adapters!r}\naddon = {addon!r}\n" + PATCH_BODY


def patch_existing_runtime(dry_run=True):
    import frappe
    from frappe.utils.safe_exec import safe_exec

    frappe.only_for("System Manager")
    safe_exec(console_script(dry_run=dry_run), script_filename="SS97 payment runtime installer")
