"""Pure validation rules for CyberOS company records. No network or active scan."""
import re
from uuid import UUID

KINDS = ("WORKSTATION", "SERVER", "NETWORK", "CLOUD", "SOFTWARE", "OTHER")
CRITICALITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
ACTION_CATEGORIES = ("ACCESS", "BACKUP", "UPDATES", "ENDPOINT", "NETWORK",
                     "TRAINING", "INCIDENT", "SUPPLIERS", "OTHER")
SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
CLIENT_ACTION_STATES = ("OPEN", "IN_PROGRESS", "DONE_DECLARED")
PASSWORD_PATTERN = re.compile(
    r"(?i)\b(password|mot de passe|secret|token|clé privée|private key|api[_ -]?key)"
    r"\s*[:=]"
)


def text(value, length=160, label="Information"):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > length:
        raise ValueError(label + " invalide.")
    value = value.strip()
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValueError(label + " invalide.")
    if PASSWORD_PATTERN.search(value):
        raise ValueError("Ne saisissez aucun mot de passe ou secret.")
    return value


def choice(value, allowed, label="Valeur"):
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(label + " invalide.")
    return value


def identifier(value):
    if not isinstance(value, str) or len(value) != 36:
        raise ValueError("Identifiant invalide.")
    try:
        canonical = str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise ValueError("Identifiant invalide.") from exc
    if canonical != value:
        raise ValueError("Identifiant invalide.")
    return canonical


def asset_data(label, kind, criticality, business_service):
    return {
        "label": text(label, 120, "Équipement"),
        "kind": choice(kind, KINDS, "Type d'équipement"),
        "criticality": choice(criticality, CRITICALITIES, "Criticité"),
        "business_service": text(business_service, 120, "Service métier"),
    }


def action_data(summary, category, priority, asset=None):
    if asset not in (None, ""):
        asset = identifier(asset)
    return {
        "summary": text(summary, 240, "Mesure corrective"),
        "category": choice(category, ACTION_CATEGORIES, "Catégorie"),
        "priority": choice(priority, SEVERITIES, "Priorité"),
        "asset": asset or None,
    }


def incident_data(summary, severity, description):
    return {
        "summary": text(summary, 160, "Incident"),
        "severity": choice(severity, SEVERITIES, "Gravité"),
        "description": text(description, 2000, "Description"),
    }
