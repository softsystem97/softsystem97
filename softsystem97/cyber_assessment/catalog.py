"""Non-binding scope catalog. Every intervention requires a separate mandate."""

import re


TIERS = {
    "ESSENTIEL": {
        "label": "Basique — état des lieux",
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
        "label": "Premium — analyse approfondie",
        "description": "Revue des configurations, identités et pratiques de résilience.",
        "checks": (
            "Tous les contrôles du niveau Basique",
            "Revues d'habilitations et comptes à privilèges",
            "Segmentation réseau et configuration du cloud",
            "Journalisation, alertes et traitement des incidents",
            "Risque fournisseur et gouvernance documentaire",
        ),
        "deliverables": ("Matrice des risques", "Plan de remédiation avec responsabilités"),
    },
    "EXTREME": {
        "label": "Ultra — résilience et gouvernance",
        "description": "Programme d'analyse renforcée sous mandat écrit et revue humaine.",
        "checks": (
            "Tous les contrôles du niveau Premium",
            "Architecture et continuité d'activité multisite",
            "Exercices de gestion de crise sur scénario approuvé",
            "Revue de la détection et de la réponse aux incidents",
            "Validation des preuves et arbitrage des risques résiduels",
        ),
        "deliverables": ("Rapport exécutif et registre de risques", "Feuille de route à 30, 60 et 90 jours"),
    },
}

REQUEST_KINDS = {
    "LIBRE": "Ticket libre", "CYBER": "Analyse cybersécurité",
    "GENERALISTE": "Assistance informatique généraliste N2",
    "BANQUE": "Assistance informatique bancaire N3",
}

# Question wording and answers are versioned so old customer self-assessments
# remain intelligible after the catalogue evolves. Answers are DECLARATIVE.
QUESTION_VERSION = "2026-11-v1"
QUESTIONS = {
    "inventory": "Disposez-vous d'un inventaire à jour des équipements et comptes ?",
    "mfa": "L'authentification multifacteur protège-t-elle les accès sensibles ?",
    "backup": "Les sauvegardes sont-elles testées par restauration ?",
    "updates": "Les systèmes et logiciels reçoivent-ils des mises à jour régulières ?",
    "endpoint": "Les postes et serveurs disposent-ils d'une protection suivie ?",
    "access": "Les droits d'accès sont-ils revus à intervalles réguliers ?",
    "network": "Les réseaux sensibles et les accès externes sont-ils séparés ?",
    "training": "Les équipes sont-elles sensibilisées au phishing ?",
    "incident": "Un plan de gestion des incidents a-t-il été testé ?",
    "suppliers": "La sécurité des fournisseurs et prestataires est-elle évaluée ?",
}
ANSWER_VALUES = {"YES": 2, "PARTIAL": 1, "NO": 0, "UNKNOWN": 0}
ANSWER_LABELS = {"YES": "Oui", "PARTIAL": "Partiellement", "NO": "Non", "UNKNOWN": "Je ne sais pas"}
EMPLOYEE_BANDS = {"1-10", "11-50", "51-250", "251-1000", "1000+"}
DATA_TYPES = {"PUBLIC", "CLIENT", "PERSONAL", "SENSITIVE"}


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
    if kind != "CYBER" and tier not in ("", None):
        raise ValueError("Seule une expertise cyber possède une formule.")
    if consent is not True:
        raise ValueError("Accord de contact explicite requis.")
    company = required_text(organization, 120, "Organisation")
    details = required_text(summary, 2000, "Besoin")
    if re.search(r"(?i)\b(password|mot de passe|secret|token|clé privée|private key)\s*[:=]", details):
        raise ValueError("Ne saisissez pas de mot de passe ou secret.")
    return {"kind": kind, "tier": tier if kind == "CYBER" else "",
            "organization": company, "summary": details}


def validate_profile(profile):
    """Accept business context, never credentials or arbitrary client objects."""
    if not isinstance(profile, dict) or set(profile) != {
        "sector", "country", "city", "employees", "sites", "devices", "contact_role", "data_type"
    }:
        raise ValueError("Formulaire entreprise incomplet.")
    result = {field: required_text(profile[field], limit, label) for field, limit, label in (
        ("sector", 100, "Secteur"), ("country", 70, "Pays"),
        ("city", 100, "Ville"), ("contact_role", 100, "Fonction du contact"),
    )}
    if profile["employees"] not in EMPLOYEE_BANDS or profile["data_type"] not in DATA_TYPES:
        raise ValueError("Taille ou sensibilité des données non reconnue.")
    for key in ("sites", "devices"):
        value = profile[key]
        if type(value) is not int or not 1 <= value <= 100000:
            raise ValueError("Nombre de sites ou de postes incorrect.")
        result[key] = value
    result["employees"] = profile["employees"]
    result["data_type"] = profile["data_type"]
    return result


def validate_answers(answers):
    if (not isinstance(answers, dict) or set(answers) != set(QUESTIONS)
            or any(not isinstance(value, str) or value not in ANSWER_VALUES
                   for value in answers.values())):
        raise ValueError("Toutes les réponses d'autodiagnostic sont requises.")
    return {key: answers[key] for key in QUESTIONS}


def self_assessment(answers):
    """Conservative self-reported indicator, never an automated certification."""
    checked = validate_answers(answers)
    score = round(100 * sum(ANSWER_VALUES[v] for v in checked.values()) /
                  (2 * len(QUESTIONS)))
    strengths = [QUESTIONS[key] for key, value in checked.items() if value == "YES"]
    priorities = [QUESTIONS[key] for key, value in checked.items() if value != "YES"]
    return {"score": score, "strengths": strengths, "priorities": priorities,
            "unknown_count": sum(v == "UNKNOWN" for v in checked.values()),
            "question_version": QUESTION_VERSION}


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
