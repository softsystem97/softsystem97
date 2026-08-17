from __future__ import annotations

import frappe

TICKET_LIBRE_SUCCESS_URL = "/suivre-mon-ticket"

TICKET_LIBRE_CLIENT_SCRIPT = r"""frappe.web_form.after_load = function() {
  document.title = 'Ticket libre — SoftSystem97';
  window.__ss97PriorityAllowed = ['Low','Medium','High','Urgent'];

  // Frappe v16 passes the inserted document only to handle_success(data).
  // Preserve it so after_save can flush the notification and build the tracking URL.
  if (!frappe.web_form.__ss97HandleSuccessPatched) {
    const originalHandleSuccess = frappe.web_form.handle_success.bind(frappe.web_form);
    frappe.web_form.handle_success = function(data) {
      window.__ss97SavedDoc = data || {};
      return originalHandleSuccess(data);
    };
    frappe.web_form.__ss97HandleSuccessPatched = true;
  }
};

frappe.web_form.validate = function() {
  const em = (frappe.web_form.get_value('ss97_contact_email') || '').trim();
  if (!em || em.indexOf('@') < 1) {
    frappe.msgprint('Adresse e-mail invalide');
    return false;
  }
  if (!frappe.web_form.get_value('ss97_terms_accepted')) {
    frappe.msgprint('Veuillez accepter les conditions');
    return false;
  }

  let prio = (frappe.web_form.get_value('priority') || '').trim();
  const map = {
    faible:'Low', basse:'Low', standard:'Low', low:'Low',
    normal:'Medium', normale:'Medium', moyen:'Medium', moyenne:'Medium',
    prioritaire:'Medium', medium:'Medium',
    haute:'High', high:'High',
    urgent:'Urgent', urgente:'Urgent', critique:'Urgent', critical:'Urgent'
  };
  const allowed = window.__ss97PriorityAllowed || ['Low','Medium','High','Urgent'];
  if (map[prio.toLowerCase()]) prio = map[prio.toLowerCase()];
  if (allowed.indexOf(prio) < 0) {
    frappe.msgprint('Priorité invalide');
    return false;
  }

  frappe.web_form.set_value('priority', prio);
  frappe.web_form.set_value('raised_by', em);
  frappe.web_form.set_value('ss97_support_inbox', 'contact@softsystem97.com');
  if (!frappe.web_form.get_value('ss97_ticket_status')) {
    frappe.web_form.set_value('ss97_ticket_status', 'Nouveau');
  }
  if (!frappe.web_form.get_value('ss97_source')) {
    frappe.web_form.set_value('ss97_source', 'Portail');
  }

  // The server-side After Insert script owns the collision-resistant public reference.
  frappe.web_form.set_value('ss97_public_ref', '');
  return true;
};

frappe.web_form.after_save = function() {
  const doc = window.__ss97SavedDoc || frappe.web_form.doc || {};
  const ref = doc.ss97_public_ref || doc.name || '';
  const email = doc.ss97_contact_email || doc.raised_by || '';
  let redirected = false;

  function go() {
    if (redirected) return;
    redirected = true;
    const params = new URLSearchParams({
      created: '1',
      ref: ref,
      email: email
    });
    window.location.href = '/suivre-mon-ticket?' + params.toString();
  }

  // Idempotent server endpoint: sends immediately when possible and leaves
  // the Issue pending for the worker when the mail provider is unavailable.
  if (typeof frappe !== 'undefined' && frappe.call && doc.name) {
    frappe.call({
      method: 'ss97_ticket_brevo_flush',
      args: { name: doc.name },
      freeze: false,
      callback: go,
      error: go
    });
    setTimeout(go, 8000);
  } else {
    go();
  }
};
"""

TICKET_LIBRE_AFTER_INSERT_SCRIPT = r"""# SoftSystem97 — After Insert: collision-resistant reference, tracking token, email persistence
RANDOM_SQL = "select sha2(concat(rand(), uuid(), now(6)), 256) as h"

try:
    d = doc

    if not (d.ss97_public_ref and str(d.ss97_public_ref).startswith("SS97-TKT-")):
        random_ref = str(frappe.db.sql(RANDOM_SQL, as_dict=True)[0]["h"])[:10].upper()
        d.db_set("ss97_public_ref", "SS97-TKT-" + random_ref, update_modified=False)

    if not d.ss97_follow_token:
        follow_token = str(frappe.db.sql(RANDOM_SQL, as_dict=True)[0]["h"])[:40]
        d.db_set("ss97_follow_token", follow_token, update_modified=False)
        d.db_set(
            "ss97_follow_token_expires",
            frappe.utils.add_days(frappe.utils.now_datetime(), 30),
            update_modified=False,
        )

    if not (d.ss97_email_sent_on or d.ss97_email_sent):
        email = (d.ss97_contact_email or d.raised_by or "").strip()
        if email and "@" in email:
            d.db_set("ss97_email_delivery_status", "pending", update_modified=False)
            d.db_set("ss97_email_error_message", "", update_modified=False)
        else:
            d.db_set("ss97_email_delivery_status", "failed", update_modified=False)
            d.db_set("ss97_email_error_message", "invalid_or_missing_email", update_modified=False)
except Exception:
    frappe.log_error(frappe.get_traceback(), "SS97 After Insert Number Token")
"""


AI_RECEPTION_SCRIPT_NAME = "SS97 AI Agent Reception After Insert"
AI_CATEGORY_OVERWRITE = '    frappe.db.set_value("Issue", doc.name, "ss97_category", cat_map.get(category, "Autre"), update_modified=False)'
AI_CATEGORY_PRESERVE = '''    if not (doc.ss97_category or "").strip():
        frappe.db.set_value("Issue", doc.name, "ss97_category", cat_map.get(category, "Autre"), update_modified=False)'''
AI_PRIORITY_OVERWRITE = '    frappe.db.set_value("Issue", doc.name, "priority", prio_map.get(urgency, "Medium"), update_modified=False)'
AI_PRIORITY_PRESERVE = '''    if not (doc.priority or "").strip():
        frappe.db.set_value("Issue", doc.name, "priority", prio_map.get(urgency, "Medium"), update_modified=False)'''


def _preserve_explicit_ticket_choices(script: str) -> str:
    if AI_CATEGORY_PRESERVE not in script:
        if AI_CATEGORY_OVERWRITE not in script:
            frappe.throw("Expected AI category assignment was not found")
        script = script.replace(AI_CATEGORY_OVERWRITE, AI_CATEGORY_PRESERVE, 1)

    if AI_PRIORITY_PRESERVE not in script:
        if AI_PRIORITY_OVERWRITE not in script:
            frappe.throw("Expected AI priority assignment was not found")
        script = script.replace(AI_PRIORITY_OVERWRITE, AI_PRIORITY_PRESERVE, 1)

    return script


def execute() -> None:
    if frappe.db.exists("Web Form", "ss97-ouvrir-ticket"):
        frappe.db.set_value(
            "Web Form",
            "ss97-ouvrir-ticket",
            {
                "success_url": TICKET_LIBRE_SUCCESS_URL,
                "client_script": TICKET_LIBRE_CLIENT_SCRIPT,
            },
            update_modified=True,
        )

    if frappe.db.exists("Server Script", "SS97 Issue After Insert Number Token"):
        frappe.db.set_value(
            "Server Script",
            "SS97 Issue After Insert Number Token",
            "script",
            TICKET_LIBRE_AFTER_INSERT_SCRIPT,
            update_modified=True,
        )

    if frappe.db.exists("Server Script", AI_RECEPTION_SCRIPT_NAME):
        ai_script = frappe.get_doc("Server Script", AI_RECEPTION_SCRIPT_NAME)
        preserved_script = _preserve_explicit_ticket_choices(ai_script.script or "")
        if preserved_script != ai_script.script:
            ai_script.db_set("script", preserved_script, update_modified=True)

    frappe.clear_cache(doctype="Web Form")
