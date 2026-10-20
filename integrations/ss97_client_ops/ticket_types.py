# -*- coding: utf-8 -*-
"""Types de tickets Phase 6 — Mission 1."""
from __future__ import annotations

from typing import Any

TICKET_KINDS = [
    ("libre", "Ticket Libre", "Medium", "À distance"),
    ("client", "Ticket Client", "Medium", "À distance"),
    ("urgence", "Ticket d'urgence", "Urgent", "À distance"),
    ("planifie", "Ticket planifié", "Medium", "Sur site"),
    ("maintenance", "Ticket de maintenance", "Low", "Sur site"),
    ("distance", "Ticket à distance", "Medium", "À distance"),
    ("site", "Ticket sur site", "Medium", "Sur site"),
]


def infer_ticket_kind(subject: str = "", description: str = "", priority: str = "") -> str:
    text = f"{subject} {description} {priority}".lower()
    if "urgent" in text or "urgence" in text or priority == "Urgent":
        return "urgence"
    if "maintenance" in text or "prévent" in text or "prevent" in text:
        return "maintenance"
    if "planif" in text or "rendez-vous" in text or "rdv" in text:
        return "planifie"
    if "sur site" in text or "onsite" in text or "déplacement" in text:
        return "site"
    if "distance" in text or "remote" in text or "à distance" in text:
        return "distance"
    if "libre" in text or "onboarding" in text:
        return "libre"
    return "client"


def create_typed_ticket(
    client,
    *,
    customer: str,
    kind: str = "client",
    subject: str = "",
    description: str = "",
    category: str = "Assistance informatique",
    raised_by: str = "contact@softsystem97.com",
) -> dict[str, Any]:
    from integrations.ss97_tickets.workflow_logic import next_ss97_ticket_ref, prepare_new_issue

    meta = {k: (label, prio, itype) for k, label, prio, itype in TICKET_KINDS}.get(kind)
    if not meta:
        kind = "client"
        meta = ("Ticket Client", "Medium", "À distance")
    label, priority, intervention = meta
    public_ref = next_ss97_ticket_ref(client)
    subj = (subject or f"{label} — {customer}")[:140]
    desc = description or (
        f"<p><b>{label}</b> SoftSystem97 — réf. {public_ref}</p>"
        f"<p>Type d'intervention : {intervention}. Historisation et sync portails activées.</p>"
    )
    # Catégories Issue.ss97_category (Select ERPNext) — fallback sûr
    _VALID_CATS = {
        "Assistance informatique",
        "Maintenance",
        "Microsoft 365",
        "Cybersécurité",
        "Réseau",
        "Cloud",
        "Matériel",
        "Logiciel",
        "Autre",
    }
    if category not in _VALID_CATS:
        category = "Assistance informatique"

    payload = {
        "doctype": "Issue",
        "subject": subj,
        "description": desc,
        "customer": customer,
        "priority": priority,
        "issue_type": "Support",
        "status": "Open",
        "raised_by": raised_by,
        "ss97_public_ref": public_ref,
        "ss97_ticket_status": "Nouveau",
        "ss97_category": category,
        "ss97_ai_intervention_type": intervention,
        "ss97_ticket_kind": kind,
        "ss97_ticket_kind_label": label,
    }
    # Validation/payment preparation is mandatory. Failure must prevent insertion.
    prepare_new_issue(payload)
    try:
        res = client.insert(payload)
        name = (res.get("data") or res.get("message") or {}).get("name") or res.get("name")
        return {
            "ok": bool(name),
            "name": name,
            "public_ref": public_ref,
            "kind": kind,
            "kind_label": label,
            "priority": priority,
            "intervention_type": intervention,
        }
    except Exception:
        # A transport error may follow a successful insert. Never blindly duplicate it,
        # and never publish raw remote exception text (potentially customer data).
        return {"ok": False, "error": "Création non confirmée ; vérifier la référence avant toute reprise.",
                "public_ref": public_ref}
