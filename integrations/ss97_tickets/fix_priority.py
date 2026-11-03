"""Correction définitive des priorités tickets SoftSystem97.

Cause : Issue.priority est un Link vers « Issue Priority ».
Seules Low / Medium / High existaient — le Web Form envoyait « Urgent ».
"""

from __future__ import annotations

import json
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _response_name(response):
    """Native REST response shapes; no deployment SDK needed for pure normalization."""
    if not isinstance(response, dict):
        return None
    record = response.get("data") or response.get("message") or response
    return record.get("name") if isinstance(record, dict) else None


REPORT_JSON = ROOT / "migration_export" / "TICKETS_PRIORITY_FIX_REPORT.json"
REPORT_MD = ROOT / "migration_export" / "TICKETS_PRIORITY_FIX_REPORT.md"

# Priorités officielles ERPNext SoftSystem97
CANONICAL_PRIORITIES = ["Low", "Medium", "High", "Urgent"]

# Libellés FR / alias → valeur Issue Priority
PRIORITY_ALIASES: dict[str, str] = {
    "low": "Low",
    "faible": "Low",
    "basse": "Low",
    "standard": "Low",
    "normale": "Medium",
    "normal": "Medium",
    "medium": "Medium",
    "moyen": "Medium",
    "moyenne": "Medium",
    "prioritaire": "Medium",
    "high": "High",
    "haute": "High",
    "élevée": "High",
    "elevee": "High",
    "urgent": "Urgent",
    "urgente": "Urgent",
    "critique": "Urgent",
    "critical": "Urgent",
    "crit": "Urgent",
}

WEB_FORM_PRIORITY_OPTIONS = "Low\nMedium\nHigh\nUrgent"
WEB_FORM_PRIORITY_LABELS_FR = (
    "Low — Faible / Standard (72h)\n"
    "Medium — Normal / Prioritaire (24h)\n"
    "High — Haute (8h)\n"
    "Urgent — Urgent / Critique (2h)"
)


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def _client():
    from migrate_odoo_erpnext.erpnext_client import ERPNextClient

    c = ERPNextClient.from_env()
    c.ping()
    return c


def _get(client, doctype: str, name: str) -> dict | None:
    try:
        dt = urllib.parse.quote(doctype, safe="")
        enc = urllib.parse.quote(name, safe="")
        return client.request("GET", f"/api/resource/{dt}/{enc}/").get("data")
    except Exception:  # noqa: BLE001 -- unavailable private response is not logged
        return None


def normalize_priority(value: str | None, *, allowed: list[str] | None = None) -> str:
    """Mappe n'importe quel libellé vers une Issue Priority valide."""
    allowed = CANONICAL_PRIORITIES if allowed is None else allowed
    if not allowed or not isinstance(allowed, (list, tuple)):
        raise ValueError("Liste de priorités autorisées vide ou invalide.")
    if not all(isinstance(item, str) and item for item in allowed):
        raise ValueError("Liste de priorités autorisées invalide.")
    raw = (value or "").strip()
    if not raw:
        if "Low" in allowed:
            return "Low"
        raise ValueError(
            "Priorité par défaut indisponible dans les valeurs autorisées."
        )
    if raw in allowed:
        return raw
    mapped = PRIORITY_ALIASES.get(raw.lower())
    if mapped and mapped in allowed:
        return mapped
    # fuzzy
    low = raw.lower()
    for a in allowed:
        if a.lower() == low:
            return a
    if "Low" in allowed:
        return "Low"
    raise ValueError("Priorité non disponible dans les valeurs autorisées.")


def list_issue_priorities(client) -> list[str]:
    rows = client.list_docs("Issue Priority", fields=["name"], limit=50)
    return [r["name"] for r in rows]


def ensure_issue_priorities(client) -> dict[str, str]:
    out: dict[str, str] = {}
    existing = set(list_issue_priorities(client))
    for name in CANONICAL_PRIORITIES:
        if name in existing:
            out[name] = "exists"
            continue
        try:
            client.insert(
                {
                    "doctype": "Issue Priority",
                    "name": name,
                    "description": f"Priorité SoftSystem97 — {name}",
                }
            )
            out[name] = "created"
        except Exception:  # noqa: BLE001 -- an SDK error can follow a committed insert
            # Read back; never blindly retry a potentially successful remote write.
            observed = _get(client, "Issue Priority", name)
            out[name] = (
                "exists_after_error"
                if isinstance(observed, dict) and observed.get("name") == name
                else "err:priority_creation_failed"
            )
    return out


def fix_web_form(client, allowed: list[str]) -> dict[str, Any]:
    """Met à jour le Web Form ouvrir-ticket : options = priorités réelles + validation JS."""
    route = "ouvrir-ticket"
    rows = client.list_docs(
        "Web Form", filters=[["route", "=", route]], fields=["name"], limit=5
    )
    if not rows:
        # also check ticket-libre related forms
        return {"ok": False, "error": "web_form_missing"}

    options = "\n".join(allowed)
    client_script = (
        "frappe.web_form.after_load = function() {\n"
        "  document.title = 'Ticket libre — SoftSystem97';\n"
        "  const allowed = " + json.dumps(allowed) + ";\n"
        "  window.__ss97PriorityAllowed = allowed;\n"
        "};\n"
        "frappe.web_form.validate = function() {\n"
        "  const em = (frappe.web_form.get_value('ss97_contact_email') || '').trim();\n"
        "  if (!em || em.indexOf('@') < 1) { frappe.msgprint('Adresse e-mail invalide'); return false; }\n"
        "  if (!frappe.web_form.get_value('ss97_terms_accepted')) {\n"
        "    frappe.msgprint('Veuillez accepter les conditions'); return false;\n"
        "  }\n"
        "  let prio = (frappe.web_form.get_value('priority') || '').trim();\n"
        "  const map = {\n"
        "    'faible':'Low','basse':'Low','standard':'Low','low':'Low',\n"
        "    'normal':'Medium','normale':'Medium','moyen':'Medium','moyenne':'Medium',\n"
        "    'prioritaire':'Medium','medium':'Medium',\n"
        "    'haute':'High','élevée':'High','elevee':'High','high':'High',\n"
        "    'urgent':'Urgent','urgente':'Urgent','critique':'Urgent','critical':'Urgent'\n"
        "  };\n"
        "  const allowed = window.__ss97PriorityAllowed || ['Low','Medium','High','Urgent'];\n"
        "  if (map[prio.toLowerCase()]) prio = map[prio.toLowerCase()];\n"
        "  if (allowed.indexOf(prio) < 0) {\n"
        "    frappe.msgprint('Priorité invalide. Choisissez : ' + allowed.join(', '));\n"
        "    return false;\n"
        "  }\n"
        "  frappe.web_form.set_value('priority', prio);\n"
        "  frappe.web_form.set_value('raised_by', em);\n"
        "  if (!frappe.web_form.get_value('ss97_public_ref')) {\n"
        "    const hex = (Math.random().toString(16) + '00000000').slice(2, 10).toUpperCase();\n"
        "    frappe.web_form.set_value('ss97_public_ref', 'TKT-' + hex);\n"
        "  }\n"
        "  if (!frappe.web_form.get_value('ss97_ticket_status'))\n"
        "    frappe.web_form.set_value('ss97_ticket_status', 'Nouveau');\n"
        "  if (!frappe.web_form.get_value('ss97_source'))\n"
        "    frappe.web_form.set_value('ss97_source', 'Portail');\n"
        "  return true;\n"
        "};\n"
        "frappe.web_form.on_success = function(doc) {\n"
        "  const ref = doc.ss97_public_ref || doc.name || '';\n"
        "  const email = doc.ss97_contact_email || doc.raised_by || '';\n"
        "  if (ref) {\n"
        "    window.location.href = '/suivre-mon-ticket?created=1&ref=' + encodeURIComponent(ref)\n"
        "      + '&email=' + encodeURIComponent(email);\n"
        "  }\n"
        "};\n"
    )

    results: dict[str, Any] = {}
    for row in rows:
        full = _get(client, "Web Form", row["name"])
        if not full:
            results[row["name"]] = "missing"
            continue
        fields = full.get("web_form_fields") or []
        updated = False
        for f in fields:
            if f.get("fieldname") == "priority":
                f["fieldtype"] = "Select"
                f["options"] = options
                f["default"] = "Low" if "Low" in allowed else allowed[0]
                f["reqd"] = 1
                updated = True
        if not updated:
            fields.append(
                {
                    "fieldname": "priority",
                    "fieldtype": "Select",
                    "label": "Priorité",
                    "options": options,
                    "default": "Low",
                    "reqd": 1,
                    "idx": 8,
                }
            )
        full["web_form_fields"] = fields
        full["client_script"] = client_script
        full["introduction_text"] = (
            "<h2>Ticket libre — Demande d'assistance</h2>"
            "<p>Priorités disponibles : "
            "<b>Low</b> (Faible/Standard 72h), "
            "<b>Medium</b> (Normal/Prioritaire 24h), "
            "<b>High</b> (Haute 8h), "
            "<b>Urgent</b> (Urgent/Critique 2h).</p>"
            "<p><a href='/conditions-generales' target='_blank'>Conditions générales</a></p>"
        )
        full["published"] = 1
        try:
            client.save(full)
            results[row["name"]] = "updated"
        except Exception:  # noqa: BLE001 -- redact unknown SDK/provider errors
            results[row["name"]] = "err:remote_operation_failed"
    return {"ok": True, "forms": results, "options": options}


def fix_other_ticket_webforms(client, allowed: list[str]) -> dict[str, str]:
    """Aligne tout Web Form lié à Issue / ticket."""
    out: dict[str, str] = {}
    rows = client.list_docs(
        "Web Form",
        filters=[["doc_type", "=", "Issue"]],
        fields=["name", "route"],
        limit=30,
    )
    options = "\n".join(allowed)
    for row in rows:
        full = _get(client, "Web Form", row["name"])
        if not full:
            continue
        changed = False
        for f in full.get("web_form_fields") or []:
            if f.get("fieldname") == "priority":
                if f.get("options") != options:
                    f["options"] = options
                    f["default"] = "Low"
                    changed = True
                # purge invalid default
                if f.get("default") and f["default"] not in allowed:
                    f["default"] = "Low"
                    changed = True
        if changed:
            try:
                client.save(full)
                out[row.get("route") or row["name"]] = "updated"
            except Exception:  # noqa: BLE001 -- redact unknown SDK/provider errors
                out[row.get("route") or row["name"]] = "err:remote_operation_failed"
        else:
            out[row.get("route") or row["name"]] = "ok"
    return out


def sanitize_existing_issues(client, allowed: list[str]) -> dict[str, Any]:
    """Corrige les Issues dont priority est vide ou invalide (sans toucher le reste)."""
    rows = client.list_docs("Issue", fields=["name", "priority"], limit=200)
    fixed = 0
    failed = 0
    scanned = 0
    for r in rows:
        scanned += 1
        p = r.get("priority")
        if p in allowed:
            continue
        if not p:
            continue  # leave empty ok
        # invalid priority string
        new_p = normalize_priority(p, allowed=allowed)
        if new_p == p:
            continue
        try:
            full = _get(client, "Issue", r["name"])
            if not full:
                continue
            full["priority"] = new_p
            client.save(full)
            fixed += 1
        except Exception:  # noqa: BLE001 -- report count only, no private payload
            failed += 1
    return {"scanned": scanned, "fixed": fixed, "failed": failed}


def test_create_all_priorities(client, allowed: list[str]) -> dict[str, Any]:
    from integrations.ss97_tickets.workflow_logic import prepare_new_issue

    results: dict[str, Any] = {}
    ts = datetime.now(timezone.utc).strftime("%H%M%S")
    for prio in allowed:
        try:
            doc = prepare_new_issue(
                {
                    "doctype": "Issue",
                    "subject": f"[PRIO-FIX] {prio} {ts}",
                    "description": f"Test priorité {prio} SoftSystem97",
                    "priority": prio,
                    "ss97_category": "Assistance informatique",
                    "ss97_contact_email": f"prio-{prio.lower()}-{ts}@example.invalid",
                    "ss97_source": "Desk",
                    "raised_by": f"prio-{prio.lower()}-{ts}@example.invalid",
                }
            )
            # Force sanitize
            doc["priority"] = normalize_priority(doc.get("priority"), allowed=allowed)
            res = client.insert(doc)
            name = _response_name(res)
            full = _get(client, "Issue", name) if name else None
            got = (full or {}).get("priority")
            results[prio] = {
                "ok": bool(name) and got == prio,
                "name": name,
                "saved_priority": got,
            }
        except Exception:  # noqa: BLE001 -- redact unknown SDK/provider errors
            results[prio] = {"ok": False, "error": "test_creation_failed"}
    return results


def write_report(report: dict[str, Any]) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    tests = report.get("tests") or {}
    md = f"""# SoftSystem97 — Correction priorités tickets

**Date :** {report.get("at")}  
**Instance :** {report.get("instance")}  
**OK :** {"OUI" if report.get("ok") else "NON"}

## Cause
`Issue.priority` est un **Link** vers `Issue Priority`.  
Seules **Low / Medium / High** existaient. Le formulaire Web envoyait **Urgent** → erreur système.

## Priorités ERPNext
`{report.get("priorities_before")}` → `{report.get("priorities_after")}`

Création : `{json.dumps(report.get("ensure_priorities"), ensure_ascii=False)}`

## Web Forms
`{json.dumps(report.get("web_form"), ensure_ascii=False)}`

Autres formulaires Issue : `{json.dumps(report.get("other_webforms"), ensure_ascii=False)}`

## Mapping
- Faible / Standard / Low → **Low**
- Normal / Prioritaire / Medium → **Medium**
- Haute / High → **High**
- Urgent / Critique → **Urgent**

## Tests création
{chr(10).join(f"- **{k}** : {'OK' if v.get('ok') else 'KO'} — `{v.get('name') or v.get('error')}` (sauvé={v.get('saved_priority')})" for k, v in tests.items())}

## Issues corrigées
`{json.dumps(report.get("sanitize_issues"), ensure_ascii=False)}`

## Relance
```bash
python -m integrations.ss97_tickets.fix_priority
```
"""
    REPORT_MD.write_text(md, encoding="utf-8")


def run(
    *, apply_changes=False, create_test_tickets=False, client=None
) -> dict[str, Any]:
    """Preview by default. Historical bulk remediation needs explicit operator approval."""
    if type(apply_changes) is not bool or type(create_test_tickets) is not bool:
        raise ValueError("Options booléennes explicites requises.")
    if create_test_tickets and not apply_changes:
        raise ValueError(
            "La création de tickets de test exige une application approuvée."
        )
    client = _client() if client is None else client
    report: dict[str, Any] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "instance": "not_exported",
        "mode": "apply" if apply_changes else "preview",
    }

    log("1/5 Lecture priorités existantes…")
    before = list_issue_priorities(client)
    report["priorities_before"] = before

    if not apply_changes:
        report["planned_priorities"] = [
            p for p in CANONICAL_PRIORITIES if p not in before
        ]
        report["writes_performed"] = False
        return report

    log("2/5 Création priorités manquantes (dont Urgent)…")
    report["ensure_priorities"] = ensure_issue_priorities(client)
    after = list_issue_priorities(client)
    report["priorities_after"] = after
    allowed = [p for p in CANONICAL_PRIORITIES if p in after]
    if not allowed:
        allowed = after or ["Low", "Medium", "High"]
    report["allowed"] = allowed

    log("3/5 Correction Web Form ouvrir-ticket…")
    report["web_form"] = fix_web_form(client, allowed)
    report["other_webforms"] = fix_other_ticket_webforms(client, allowed)
    try:
        from integrations.ss97_tickets.finalize import deploy_priority_guard_script

        report["priority_guard_script"] = deploy_priority_guard_script(client)
    except Exception:  # noqa: BLE001 -- redact unknown SDK/provider errors
        report["priority_guard_script"] = "err:remote_operation_failed"

    log("4/5 Sanitisation Issues existantes…")
    report["sanitize_issues"] = sanitize_existing_issues(client, allowed)

    log("5/5 Tests création Low/Medium/High/Urgent…")
    report["tests"] = (
        test_create_all_priorities(client, allowed) if create_test_tickets else {}
    )
    report["tests_executed"] = create_test_tickets
    report["ok"] = (
        create_test_tickets
        and all(v.get("ok") for v in report["tests"].values())
        and "Urgent" in after
    )

    write_report(report)
    log(f"Rapport → {REPORT_MD}")
    log(f"OK={report['ok']} priorités={after}")
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=" * 64)
    print("SOFTSYSTEM97 — FIX PRIORITÉ URGENT (Issue Priority)")
    print("=" * 64)
    import argparse

    parser = argparse.ArgumentParser(
        description="Historical priority remediation; preview by default"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Explicitly approve bulk writes on the authorized site",
    )
    parser.add_argument(
        "--create-test-tickets",
        action="store_true",
        help="Only for explicitly approved fictional recipients",
    )
    args = parser.parse_args()
    if args.create_test_tickets and not args.apply:
        parser.error("--create-test-tickets requires --apply")
    report = run(apply_changes=args.apply, create_test_tickets=args.create_test_tickets)
    if not args.apply:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
