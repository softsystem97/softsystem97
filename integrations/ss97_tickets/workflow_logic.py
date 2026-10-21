"""Logique métier tickets — transitions, SLA, références publiques."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from integrations.ss97_tickets.specs import (
    DT_ISSUE,
    PRIORITY_MAP,
    SLA_HOURS,
    STATUS_TO_NATIVE,
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def public_ref() -> str:
    """Référence publique lisible (complétée ensuite en SS97-TKT-######)."""
    return f"TKT-{secrets.token_hex(4).upper()}"


# Réserve process-local pour éviter 2× le même numéro avant insert DB
_LAST_ISSUED_N = 0


def next_ss97_ticket_ref(client) -> str:
    """Propose une référence ; l’unicité concurrente exige une contrainte serveur.

    La réserve locale ne sérialise pas plusieurs processus/clients.
    Une lecture distante échouée ne prouve jamais qu’une référence est libre.
    """
    import json
    import re
    import urllib.parse

    global _LAST_ISSUED_N

    max_n = 0
    try:
        qs = urllib.parse.urlencode(
            {
                "fields": json.dumps(["ss97_public_ref"]),
                "filters": json.dumps([["ss97_public_ref", "like", "SS97-TKT-%"]]),
                "order_by": "ss97_public_ref desc",
                "limit_page_length": "50",
            }
        )
        res = client.request("GET", f"/api/resource/Issue/?{qs}")
        rows = res.get("data") or []
        for r in rows:
            ref = (r.get("ss97_public_ref") or "").strip().upper()
            # Uniquement SS97-TKT-###### (ignore SS97-TKT-PAY-… / suffixes)
            m = re.fullmatch(r"SS97-TKT-(\d{6})", ref)
            if m:
                max_n = max(max_n, int(m.group(1)))
    except Exception:  # noqa: BLE001 -- legacy SDK errors are never disclosed
        # Fallback: échantillon large sans order_by
        try:
            rows = (
                client.list_docs(
                    DT_ISSUE,
                    filters=[["ss97_public_ref", "like", "SS97-TKT-%"]],
                    fields=["ss97_public_ref"],
                    limit=500,
                )
                or []
            )
            for r in rows:
                ref = (r.get("ss97_public_ref") or "").strip().upper()
                m = re.fullmatch(r"SS97-TKT-(\d{6})", ref)
                if m:
                    max_n = max(max_n, int(m.group(1)))
        except Exception:  # noqa: BLE001 -- availability is checked separately below
            max_n = 0

    max_n = max(max_n, _LAST_ISSUED_N)

    # Garantir unicité (évite collision si list incomplète)
    for _ in range(40):
        max_n += 1
        candidate = f"SS97-TKT-{max_n:06d}"
        try:
            existing = (
                client.list_docs(
                    DT_ISSUE,
                    filters=[["ss97_public_ref", "=", candidate]],
                    fields=["name"],
                    limit=1,
                )
                or []
            )
            if not existing:
                _LAST_ISSUED_N = max_n
                return candidate
        except Exception:  # noqa: BLE001 -- redact SDK response details
            raise RuntimeError(
                "Disponibilité de la référence non vérifiable ; création interrompue."
            ) from None
    raise RuntimeError(
        "Aucune référence disponible dans la fenêtre vérifiée ; création interrompue."
    )


def sla_deadline(priority: str) -> str:
    hours = SLA_HOURS.get(priority or "Low", 72)
    dt = datetime.now(timezone.utc) + timedelta(hours=hours)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def map_portal_priority(label: str) -> str:
    """Mappe un libellé portail vers une Issue Priority ERPNext valide."""
    from integrations.ss97_tickets.fix_priority import normalize_priority

    if label in PRIORITY_MAP:
        return PRIORITY_MAP[label]
    mapped = PRIORITY_MAP.get((label or "").strip())
    if mapped:
        return mapped
    return normalize_priority(label)


def prepare_new_issue(doc: dict[str, Any]) -> dict[str, Any]:
    doc = dict(doc)
    if not doc.get("ss97_ticket_status"):
        doc["ss97_ticket_status"] = "Nouveau"
    native = STATUS_TO_NATIVE.get(doc["ss97_ticket_status"], "Open")
    doc["status"] = native
    # Sanitize priority → Issue Priority Link
    from integrations.ss97_tickets.fix_priority import normalize_priority

    doc["priority"] = normalize_priority(doc.get("priority"))
    if not doc.get("ss97_public_ref"):
        doc["ss97_public_ref"] = public_ref()
    if not doc.get("ss97_source"):
        doc["ss97_source"] = "Desk"
    if not doc.get("ss97_sla_deadline"):
        doc["ss97_sla_deadline"] = sla_deadline(doc.get("priority") or "Low")
    if not doc.get("issue_type"):
        doc["issue_type"] = "Support"
    return doc


def build_issue_from_webform(data: dict[str, Any]) -> dict[str, Any]:
    first = (data.get("first_name") or "").strip()
    last = (data.get("last_name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    subject = (data.get("subject") or "Demande assistance").strip()
    description = (data.get("description") or "").strip()
    category = data.get("category") or "Assistance informatique"
    urgency = data.get("urgency") or "Standard"

    doc = {
        "doctype": DT_ISSUE,
        "subject": subject[:140],
        "description": description,
        "priority": map_portal_priority(urgency),
        "ss97_category": category,
        "ss97_contact_email": email,
        "ss97_contact_phone": phone,
        "ss97_source": "Portail",
        "raised_by": email or "guest@softsystem97.com",
    }
    if first or last:
        doc["subject"] = f"{subject} — {first} {last}".strip()[:140]
    return prepare_new_issue(doc)


def add_comment(
    client, issue_name: str, content: str, user: str = "Administrator"
) -> str | None:
    """Require native Issue read before creating a native Comment with this SDK identity."""
    from urllib.parse import quote

    try:
        result = client.request(
            "GET", f"/api/resource/Issue/{quote(issue_name, safe='')}"
        )
        issue = result.get("data") or result.get("message") or result
        if not isinstance(issue, dict) or issue.get("name") != issue_name:
            return None
        res = client.insert(
            {
                "doctype": "Comment",
                "comment_type": "Comment",
                "reference_doctype": DT_ISSUE,
                "reference_name": issue_name,
                "content": content,
                "comment_email": user,
            }
        )
        record = res.get("data") or res.get("message") or res
        return record.get("name") if isinstance(record, dict) else None
    except Exception:  # noqa: BLE001 -- no raw upstream error or blind retry
        return None
