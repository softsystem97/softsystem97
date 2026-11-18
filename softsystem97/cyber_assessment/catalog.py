"""Non-binding scope catalog. Every intervention requires a separate mandate."""

import re


TIERS = {
    "ESSENTIEL": {
        "label": "Essentiel — état des lieux",
        "description": "Cartographie déclarative et priorités de sécurité accessibles.",
        "checks": (
            "Inventaire des postes, comptes et services déclarés",
            "Mises à jour, antivirus et protection des terminaux",
            "Sauvegardes, restauration et accès aux données",
            "MFA, mots de passe et sensibilisation",
        ),
        "deliverables": ("Compte rendu de diagnostic", "Plan de corrections priorisées"),
    },
    "SUPERIEUR": {
        "label": "Supérieur — analyse approfondie",
        "description": "Revue des configurations, identités et pratiques de résilience.",
        "checks": (
            "Tous les contrôles du niveau Essentiel",
            "Revues d'habilitations et comptes à privilèges",
            "Segmentation réseau et configuration du cloud",
            "Journalisation, alertes et traitement des incidents",
            "Risque fournisseur et gouvernance documentaire",
        ),
        "deliverables": ("Matrice des risques", "Plan de remédiation avec responsabilités"),
    },
    "EXTREME": {
        "label": "Extrême — résilience et gouvernance",
        "description": "Programme d'analyse renforcée sous mandat écrit et revue humaine.",
        "checks": (
            "Tous les contrôles du niveau Supérieur",
            "Architecture et continuité d'activité multisite",
            "Exercices de gestion de crise sur scénario approuvé",
            "Revue de la détection et de la réponse aux incidents",
            "Validation des preuves et arbitrage des risques résiduels",
        ),
        "deliverables": ("Rapport exécutif et registre de risques", "Feuille de route à 30, 60 et 90 jours"),
    },
}

REQUEST_KINDS = {"LIBRE": "Ticket libre", "CYBER": "Analyse cybersécurité"}


def required_text(value, limit, label):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(f"{label} invalide.")
    cleaned = value.strip()
    if any(ord(char) < 32 and char not in "\n\t" for char in cleaned):
        raise ValueError(f"{label} invalide.")
    return cleaned


def request_payload(kind, tier, organization, summary, consent):
    """Strict input boundary: requests never authorize a scan or remote session."""
    if kind not in REQUEST_KINDS:
        raise ValueError("Type de demande inconnu.")
    if kind == "CYBER" and tier not in TIERS:
        raise ValueError("Formule cybersécurité inconnue.")
    if kind == "LIBRE" and tier not in ("", None):
        raise ValueError("Un ticket libre n'a pas de formule cyber.")
    if consent is not True:
        raise ValueError("Accord de contact explicite requis.")
    company = required_text(organization, 120, "Organisation")
    details = required_text(summary, 2000, "Besoin")
    if re.search(r"(?i)\b(password|mot de passe|secret|token|clé privée|private key)\s*[:=]", details):
        raise ValueError("Ne saisissez pas de mot de passe ou secret.")
    return {"kind": kind, "tier": tier if kind == "CYBER" else "",
            "organization": company, "summary": details}


def build_ticket(data):
    """Visible, auditable ticket content; *not* a testing authorization."""
    kind = data["kind"]
    tier = data["tier"]
    subject = f"[SS97-{kind}] " + data["organization"]
    if tier:
        subject += " — " + tier
    description = (
        "Demande Soft System 97\n"
        f"Type : {REQUEST_KINDS[kind]}\n"
        f"Organisation : {data['organization']}\n"
        f"Formule : {TIERS[tier]['label'] if tier else 'Sans formule'}\n"
        f"Besoin : {data['summary']}\n"
        "Consentement : être recontacté au sujet de cette demande.\n"
        "Aucun test d'intrusion, scan actif, accès distant ou paiement autorisé par ce formulaire."
    )
    return subject[:140], description
