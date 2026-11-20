"""Scoped enterprise self-assessments over the existing customer ticket bridge.

No scan, remote control, payment, credential collection or automatic certification.
The price is an indicative server snapshot; an N4 review requires a live mission.
"""

import hashlib
import json
from uuid import uuid4

import frappe

from .catalog import (TIERS, QUESTIONS, QUESTION_VERSION, build_ticket,
                      request_payload, required_text, validate_answers, validate_profile)
from .pricing import SETTINGS, TIERS_TO_FIELD, euro, snapshot

ASSESSMENT = "SS97 Cyber Assessment"


def _schema_ready():
    return all(frappe.db.exists("DocType", doctype)
               for doctype in (ASSESSMENT, SETTINGS))


def _prices():
    if not _schema_ready():
        return None
    return snapshot(frappe.get_doc(SETTINGS))


def _enabled_config():
    value = frappe.conf.get("ss97_cyber_assessment")
    return isinstance(value, dict) and value.get("enabled") is True


def _bridge_advertised():
    config = frappe.conf.get("ss97_ticket_bridge")
    return (isinstance(config, dict) and config.get("enabled") is True
            and config.get("compatibility_confirmed") is True)


def _enabled():
    if not _enabled_config():
        frappe.throw("Service en préparation : réception des demandes non activée.", frappe.PermissionError)


def _manager():
    user = frappe.session.user
    if (not user or user == "Guest"
            or not frappe.db.get_value("User", user, "enabled")
            or "System Manager" not in frappe.get_roles(user)):
        frappe.throw("Supervision réservée à la direction.", frappe.PermissionError)


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_catalog():
    """The information-only service catalog can be read without authenticating."""
    prices = _prices()
    return {"tiers": [{"code": key, **value, "price_eur": prices[key] if prices else None}
                      for key, value in TIERS.items()],
            "questions": [{"code": code, "label": label} for code, label in QUESTIONS.items()],
            "currency": "EUR", "prices_published": bool(prices),
            "active": _enabled_config() and _schema_ready() and _bridge_advertised()}


@frappe.whitelist(methods=["GET"])
def get_admin_pricing():
    _manager()
    if not _schema_ready():
        frappe.throw("Migration du module expertise requise.", frappe.PermissionError)
    doc = frappe.get_doc(SETTINGS)
    return {"basique_eur": str(doc.basique_eur or ""),
            "premium_eur": str(doc.premium_eur or ""),
            "ultra_eur": str(doc.ultra_eur or ""),
            "is_published": bool(doc.is_published),
            "intake_enabled": _enabled_config()}


@frappe.whitelist(methods=["POST"])
def set_admin_pricing(basique_eur, premium_eur, ultra_eur, publish=False):
    """Explicit manual price approval; never creates an invoice or captures funds."""
    _manager()
    if not _schema_ready():
        frappe.throw("Migration du module expertise requise.", frappe.PermissionError)
    try:
        amounts = {"basique_eur": euro(basique_eur), "premium_eur": euro(premium_eur),
                   "ultra_eur": euro(ultra_eur)}
    except ValueError as exc:
        frappe.throw(str(exc))
    published = publish is True or publish in ("true", "1", 1)
    doc = frappe.get_doc(SETTINGS)
    doc.update({**amounts, "is_published": int(published)})
    doc.save(ignore_permissions=True)  # Only a verified active System Manager reaches this write.
    return {"is_published": published, "prices": snapshot(doc)}


@frappe.whitelist(methods=["POST"])
def link_commercial_document(assessment_id, document_type, document_name):
    """Manager-only link to an EXISTING authorized ERPNext commercial document.

    Never creates a Quotation, Sales Order, invoice, payment or customer account.
    """
    _manager()
    field = {"Quotation": "quotation", "Sales Order": "sales_order",
             "Sales Invoice": "sales_invoice"}.get(document_type)
    if field is None:
        frappe.throw("Type de document commercial interdit.", frappe.PermissionError)
    try:
        name = required_text(document_name, 140, "Référence commerciale")
    except ValueError as exc:
        frappe.throw(str(exc))
    dossier = _dossier(assessment_id, lock=True)
    if not frappe.db.exists(document_type, name):
        frappe.throw("Document commercial introuvable.", frappe.PermissionError)
    commercial = frappe.get_doc(document_type, name)
    commercial.check_permission("read")
    commercial_customer = (commercial.party_name if document_type == "Quotation"
                           and commercial.quotation_to == "Customer" else
                           commercial.customer if document_type != "Quotation" else None)
    if commercial_customer != dossier.customer or int(commercial.docstatus or 0) == 2:
        frappe.throw("Document annulé ou appartenant à un autre client.", frappe.PermissionError)
    if document_type == "Sales Invoice":
        # A payment must never be offered for an unrelated or unsubmitted invoice.
        if (int(commercial.docstatus or 0) != 1
                or commercial.get("ss97_linked_issue") != dossier.ticket):
            frappe.throw("Facture soumise et liée à ce ticket obligatoire.", frappe.PermissionError)
    dossier.set(field, name)
    dossier.save(ignore_permissions=True)
    return {"assessment_id": dossier.name, "document_type": document_type,
            "document_name": name}


@frappe.whitelist(methods=["POST"])
def request_assessment(kind, tier, organization, summary, consent, request_id,
                       profile=None, answers=None):
    """Only an authenticated, uniquely bound Customer can create a request.

    Reuses the bridge's native Issue authorizations, idempotency receipt and mail.
    Neither this API nor a form grants permission to scan client infrastructure.
    """
    _enabled()
    from softsystem97.integrations.ticket_bridge import policy
    from softsystem97.integrations.ticket_bridge.api import create_ticket

    user, customer = policy.customer()  # Reject Guest, staff, unmapped or ambiguous Customer.
    accepted = consent is True or consent in ("true", "1", 1)
    try:
        payload = request_payload(kind, tier, organization, summary, accepted)
        token = required_text(request_id, 100, "Identifiant de requête")
        business = validate_profile(profile) if kind == "CYBER" else None
        controls = validate_answers(answers) if kind == "CYBER" else None
    except ValueError as exc:
        frappe.throw(str(exc))
    price = None
    fingerprint = None
    if kind == "CYBER":
        if not _schema_ready():
            frappe.throw("Module expertise non migré.", frappe.PermissionError)
        prices = _prices()
        if not prices:
            frappe.throw("Tarifs non validés par la direction.", frappe.PermissionError)
        price = prices[tier]
        fingerprint = hashlib.sha256(json.dumps(
            {"payload": payload, "profile": business, "answers": controls},
            sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    subject, description = build_ticket(payload)
    if price:
        description += f"\nEstimation indicative HT : {price} EUR, sous réserve de devis accepté."
        # The ticket bridge receipt binds the full submitted assessment, too.
        description += f"\nRéférence d'intégrité du questionnaire : {fingerprint}"
    # create_ticket rechecks customer, historic business authorization, native
    # Issue write permissions, notification recipient and request_id replay.
    ticket = create_ticket(subject, description, token)
    dossier_id = None
    if kind == "CYBER":
        existing = frappe.db.get_value(ASSESSMENT, {"ticket": ticket["name"]}, "name")
        if existing:
            dossier = frappe.get_doc(ASSESSMENT, existing, for_update=True)
            if (dossier.customer_user != user or dossier.customer != customer
                    or dossier.submission_hash != fingerprint):
                frappe.throw("Ticket déjà lié à un autre dossier d'expertise.", frappe.PermissionError)
        else:
            dossier = frappe.get_doc({
                "doctype": ASSESSMENT, "assessment_id": str(uuid4()), "ticket": ticket["name"],
                "customer": customer, "customer_user": user, "created_by_user": user,
                "organization": payload["organization"], "tier": tier,
                "price_eur": price, "currency": "EUR", "state": "RECEIVED",
                "profile_json": json.dumps(business, ensure_ascii=False, sort_keys=True),
                "answers_json": json.dumps(controls, ensure_ascii=False, sort_keys=True),
                "submission_hash": fingerprint, "question_version": QUESTION_VERSION,
            }).insert(ignore_permissions=True)
        dossier_id = dossier.name
    return {"name": ticket["name"], "status": ticket["status"],
            "kind": payload["kind"], "tier": payload["tier"],
            "assessment_id": dossier_id, "estimate_eur": price}


def _n4_authorized(doc):
    """An active, explicitly assigned N4 mission approved by a second manager."""
    from softsystem97.technician_os.api import _my_active_profile, _authorized_ticket

    profile = _my_active_profile()
    if profile.track != "CYBER":
        frappe.throw("Habilitation N4 requise.", frappe.PermissionError)
    missions = frappe.get_all("SS97 Technician Mission", filters={
        "ticket_name": doc.ticket, "technician": frappe.session.user,
        "customer": doc.customer, "track": "CYBER",
        "state": ["in", ["REPORT_SUBMITTED", "CLIENT_ACCEPTED"]],
    }, fields=["name", "authorization_reference", "approved_by"], limit_page_length=5)
    approved = next((item for item in missions
                     if item.authorization_reference and item.approved_by), None)
    if not approved:
        frappe.throw("Mission N4 approuvée, mandat et rapport requis.", frappe.PermissionError)
    # Recheck the ticket bridge's current grant: withdrawn ToDo revokes access.
    _authorized_ticket(frappe.get_doc("SS97 Technician Mission", approved.name), "technician")
    return True


def _visible(doc):
    from softsystem97.integrations.ticket_bridge import policy
    user = frappe.session.user
    if (user and user != "Guest" and frappe.db.get_value("User", user, "enabled")
            and "System Manager" in frappe.get_roles(user)):
        return "manager"
    if (user == doc.customer_user and policy.customer() == (user, doc.customer)):
        policy.authorize(frappe.get_doc("Issue", doc.ticket), "client")
        return "customer"
    _n4_authorized(doc)
    return "n4"


def _dossier(assessment_id, lock=False):
    if not isinstance(assessment_id, str) or len(assessment_id) != 36:
        frappe.throw("Dossier inconnu.", frappe.PermissionError)
    if not frappe.db.exists(ASSESSMENT, assessment_id):
        frappe.throw("Dossier introuvable.", frappe.PermissionError)
    return frappe.get_doc(ASSESSMENT, assessment_id, for_update=lock)


@frappe.whitelist(methods=["POST"])
def create_assessment_checkout(assessment_id):
    """Create Stripe Checkout for an authorized customer and matching submitted invoice.

    No credit, token, technician authorization or payment is issued by this API.
    Only the signed Stripe webhook and ERPNext ledger determine payment state.
    """
    from softsystem97.integrations.stripe.checkout import create_invoice_checkout

    dossier = _dossier(assessment_id)
    if _visible(dossier) != "customer":
        frappe.throw("Dossier inaccessible au paiement.", frappe.PermissionError)
    if not dossier.sales_invoice:
        frappe.throw("Facture non encore établie pour cette expertise.", frappe.ValidationError)
    if not frappe.get_meta("Sales Invoice").has_field("ss97_linked_issue"):
        frappe.throw("Migration des paiements manquante.", frappe.ValidationError)
    invoice = frappe.get_doc("Sales Invoice", dossier.sales_invoice)
    if (invoice.customer != dossier.customer or int(invoice.docstatus or 0) != 1
            or invoice.get("ss97_linked_issue") != dossier.ticket):
        frappe.throw("Facture et ticket non concordants.", frappe.PermissionError)
    return create_invoice_checkout(invoice.name)


@frappe.whitelist(methods=["GET"])
def get_my_assessments():
    from softsystem97.integrations.ticket_bridge import policy
    user, customer = policy.customer()
    if not _schema_ready():
        return {"assessments": []}
    rows = frappe.get_all(ASSESSMENT, filters={"customer_user": user, "customer": customer},
                          fields=["name", "ticket", "organization", "tier", "state",
                                  "price_eur", "quotation", "sales_order", "sales_invoice",
                                  "creation"], order_by="creation desc",
                          limit_page_length=100)
    # Customer rights can be revoked independently of the stored dossier.
    valid = []
    for row in rows:
        ticket = frappe.get_doc("Issue", row.ticket)
        if ticket.customer == customer and ticket.raised_by == user:
            valid.append(row)
    return {"assessments": valid}


@frappe.whitelist(methods=["GET"])
def get_n4_assessments():
    from softsystem97.technician_os.api import _my_active_profile
    profile = _my_active_profile()
    if profile.track != "CYBER":
        frappe.throw("Espace N4 réservé.", frappe.PermissionError)
    missions = frappe.get_all("SS97 Technician Mission", filters={
        "technician": frappe.session.user, "track": "CYBER",
        "state": ["in", ["REPORT_SUBMITTED", "CLIENT_ACCEPTED"]]},
        fields=["ticket_name"], limit_page_length=100)
    result = []
    for mission in missions:
        name = frappe.db.get_value(ASSESSMENT, {"ticket": mission.ticket_name}, "name")
        if name:
            doc = _dossier(name)
            try:
                _n4_authorized(doc)
            except frappe.PermissionError:
                continue
            result.append({"name": doc.name, "ticket": doc.ticket,
                           "organization": doc.organization, "tier": doc.tier,
                           "state": doc.state})
    return {"assessments": result}


@frappe.whitelist(methods=["POST"])
def review_assessment(assessment_id, decision, review_note, evidence_reference):
    dossier = _dossier(assessment_id, lock=True)
    _n4_authorized(dossier)
    if dossier.state not in ("RECEIVED", "REVISIONS_REQUIRED"):
        frappe.throw("Dossier déjà validé ou indisponible.", frappe.PermissionError)
    if decision not in ("APPROVED_N4", "REVISIONS_REQUIRED"):
        frappe.throw("Décision N4 inconnue.", frappe.PermissionError)
    try:
        note = required_text(review_note, 2000, "Motif de revue")
        reference = required_text(evidence_reference, 120, "Référence des preuves")
    except ValueError as exc:
        frappe.throw(str(exc))
    if len(note) < 40:
        frappe.throw("Expliquez votre décision en au moins 40 caractères.")
    dossier.state = decision
    dossier.reviewed_by = frappe.session.user
    dossier.reviewed_at = frappe.utils.now_datetime()
    dossier.review_note = note
    dossier.evidence_reference = reference
    dossier.save(ignore_permissions=True)
    return {"assessment_id": dossier.name, "state": dossier.state}


@frappe.whitelist(methods=["GET"])
def download_report(assessment_id):
    """Private, per-request PDF download; no public File URL or shared attachment."""
    dossier = _dossier(assessment_id)
    _visible(dossier)
    from frappe.utils.pdf import get_pdf
    from .report import report_html

    html = report_html(dossier, json.loads(dossier.profile_json),
                       json.loads(dossier.answers_json))
    pdf = get_pdf(html, options={"page-size": "A4", "encoding": "UTF-8"})
    frappe.local.response.filename = f"ss97-cyber-{dossier.name}.pdf"
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "download"


@frappe.whitelist(methods=["GET"])
def get_admin_queue():
    """Minimal cyber triage; never exposes client text to other portal users."""
    _manager()
    rows = frappe.get_all(
        "Issue", filters={"subject": ["like", "[SS97-CYBER]%"]},
        fields=["name", "subject", "status", "customer", "creation", "modified"],
        order_by="creation desc", limit_page_length=100,
    )
    if _schema_ready():
        for row in rows:
            row["assessment_id"] = frappe.db.get_value(
                ASSESSMENT, {"ticket": row["name"]}, "name")
    return {"tickets": rows, "count": len(rows)}


@frappe.whitelist(methods=["GET"])
def get_admin_readiness():
    """Read-only configuration checks without disclosing API secrets or personal data."""
    _manager()
    from softsystem97.technician_exams.readiness import MAX_ACTIVE_BANK_SIZE, audit_bank
    from softsystem97.technician_exams.rules import TRACKS as EXAM_TRACKS
    tech = frappe.conf.get("ss97_tech_os") or {}
    exams = frappe.conf.get("ss97_technician_exams") or {}
    mail = frappe.conf.get("ss97_tech_email_notifications") or {}
    bridge = frappe.conf.get("ss97_ticket_bridge") or {}
    cyber = frappe.conf.get("ss97_cyber_assessment") or {}
    cyber_schema_ready = _schema_ready()
    cyber_prices_ready = bool(_prices()) if cyber_schema_ready else False
    question_doctype = bool(frappe.db.exists("DocType", "SS97 Technician Exam Question"))
    technical_doctypes = ("SS97 Technician Profile", "SS97 Technician Mission",
                          "SS97 Technician OS Event", "SS97 Technician Document",
                          "SS97 Technician Notice", "SS97 Technician Settlement")
    tech_schema_ready = all(frappe.db.exists("DocType", name) for name in technical_doctypes)
    exam_schema_ready = question_doctype and bool(frappe.db.exists("DocType", "SS97 Technician Exam Attempt"))
    def bank_audit(track):
        if not question_doctype:
            return audit_bank([], EXAM_TRACKS[track].question_count)
        filters = {"track": track, "is_active": 1}
        try:
            total = frappe.db.count("SS97 Technician Exam Question", filters)
            rows = frappe.get_all(
                "SS97 Technician Exam Question", filters=filters,
                fields=["prompt", "options_json", "correct_option", "category"],
                limit_page_length=MAX_ACTIVE_BANK_SIZE + 1,
            )
            return audit_bank(rows, EXAM_TRACKS[track].question_count, total=total)
        except Exception:
            # An inaccessible or incomplete bank must not look deployable;
            # internal exceptions and private answers never reach the browser.
            return {"active_count": 0, "invalid_count": 0,
                    "duplicate_count": 0, "ready": False, "unavailable": True}
    audits = {track: bank_audit(track) for track in EXAM_TRACKS}
    return {"tech_os_enabled": isinstance(tech, dict) and tech.get("enabled") is True,
            "technician_schema_ready": tech_schema_ready,
            "exam_schema_ready": exam_schema_ready,
            "exams_enabled": isinstance(exams, dict) and exams.get("enabled") is True,
            "technician_email_enabled": isinstance(mail, dict) and mail.get("enabled") is True,
            "ticket_bridge_enabled": (isinstance(bridge, dict)
                                      and bridge.get("enabled") is True),
            "ticket_email_enabled": (isinstance(bridge, dict)
                                     and bridge.get("email_enabled") is True),
            "cyber_intake_enabled": (isinstance(cyber, dict)
                                    and cyber.get("enabled") is True),
            "cyber_schema_ready": cyber_schema_ready,
            "cyber_prices_published": cyber_prices_ready,
            "cyber_openai_connected": False,
            "client_notification_doctype": bool(frappe.db.exists("DocType", "SS97 Client Notification")),
            "n2_question_count": audits["L2"]["active_count"],
            "n3_question_count": audits["BANK"]["active_count"],
            "n4_question_count": audits["CYBER"]["active_count"],
            "question_bank_audit": audits,
            "question_banks_ready": all(result["ready"] for result in audits.values()),
            "stripe_connect_transfers_enabled": False}
