"""Fail-closed review of active ERPNext Issue scripts.

The allowlist is an explicit site-private inventory of independently reviewed,
exact script revisions. It MUST NOT be filled automatically on first use.
No script body or credential is returned to non-admin users.
"""
from hashlib import sha256
import json
import re

MAX_SCRIPTS = 100
DIGEST = re.compile(r"^[a-f0-9]{64}$")
REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:/-]{11,159}$")


def fingerprint(name, event, source):
    if not all(isinstance(x, str) for x in (name, event, source)):
        raise ValueError("Métadonnées de script invalides.")
    if not name.strip() or len(name) > 140 or len(source) > 200000:
        raise ValueError("Taille ou nom de script invalide.")
    value = json.dumps(
        {"name": name, "doctype_event": event, "script": source.replace("\r\n", "\n")},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    )
    return sha256(value.encode("utf-8")).hexdigest()


def approval_state(scripts, approved, reviewed, reference):
    """Exact sets of name+revision digests or fail closed, including duplicates."""
    if not isinstance(scripts, list) or len(scripts) > MAX_SCRIPTS:
        return {"approved": False, "count": -1, "unapproved": 0}
    if not scripts:
        # Empty inventories also need an explicit, independently signed review.
        # Otherwise deleting the last approved script would silently unlock
        # the bridge despite a previously pinned non-empty allowlist.
        zero_reviewed = (reviewed is True and isinstance(reference, str)
                         and REFERENCE.fullmatch(reference)
                         and isinstance(approved, dict) and not approved)
        return {"approved": bool(zero_reviewed), "count": 0,
                "unapproved": 0 if zero_reviewed else 1}
    if (reviewed is not True or not isinstance(reference, str)
            or not REFERENCE.fullmatch(reference)
            or not isinstance(approved, dict)):
        return {"approved": False, "count": len(scripts), "unapproved": len(scripts)}
    expected = {}
    try:
        for script in scripts:
            name = script["name"]
            if name in expected:
                return {"approved": False, "count": len(scripts), "unapproved": len(scripts)}
            expected[name] = fingerprint(name, script["doctype_event"], script["script"])
    except (ValueError, KeyError, TypeError):
        return {"approved": False, "count": len(scripts), "unapproved": len(scripts)}
    if set(approved) != set(expected):
        return {"approved": False, "count": len(scripts),
                "unapproved": len(set(approved) ^ set(expected))}
    mismatched = sum(
        not isinstance(approved[key], str) or not DIGEST.fullmatch(approved[key])
        or approved[key] != expected[key] for key in expected
    )
    return {"approved": mismatched == 0, "count": len(scripts), "unapproved": mismatched}


def inventory(frappe):
    """Complete set; never truncate silently when script count exceeds limit."""
    filters = {"script_type": "DocType Event", "reference_doctype": "Issue", "disabled": 0}
    total = frappe.db.count("Server Script", filters)
    if total > MAX_SCRIPTS:
        raise ValueError("Trop de scripts Issue pour vérification.")
    records = frappe.get_all(
        "Server Script", filters=filters,
        fields=["name", "doctype_event", "script"], limit_page_length=MAX_SCRIPTS + 1,
    )
    if len(records) != total:
        raise ValueError("Inventaire incomplet des scripts Issue.")
    return [dict(name=row.name, doctype_event=row.doctype_event or "", script=row.script or "")
            for row in records]
