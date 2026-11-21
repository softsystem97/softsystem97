"""Customer-only executive advisory; no external AI or Stripe calls."""
import json
import frappe
from .api import _company
from .advisory_logic import disruption_estimate, advisory

@frappe.whitelist(methods=["GET"])
def get_my_advisory():
    user, customer=_company()
    if not frappe.db.exists("DocType","SS97 Cyber Assessment"):
        return {"available":False}
    docs=frappe.get_all("SS97 Cyber Assessment",
        filters={"customer":customer,"customer_user":user},
        fields=["name","ticket","organization","answers_json"],
        order_by="creation desc",limit_page_length=10)
    from softsystem97.integrations.ticket_bridge import policy
    for row in docs:
        issue=frappe.get_doc("Issue",row.ticket)
        if issue.customer!=customer or issue.raised_by!=user:
            continue
        policy.authorize(issue,"client")
        try: result=advisory(json.loads(row.answers_json))
        except (TypeError,ValueError,KeyError): continue
        return {"available":True,"organization":row.organization,**result}
    return {"available":False}

@frappe.whitelist(methods=["POST"])
def estimate_disruption(hours,hourly_impact_eur,recovery_cost_eur):
    _company()
    try: return disruption_estimate(hours,hourly_impact_eur,recovery_cost_eur)
    except ValueError as exc: frappe.throw(str(exc),frappe.ValidationError)
