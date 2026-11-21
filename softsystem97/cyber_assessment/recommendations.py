"""Declarative enterprise cybersecurity remediation priorities; no scans or certifications."""

from .catalog import QUESTIONS, validate_answers

RECOMMENDATIONS = {
    "inventory": "Établir ou actualiser l'inventaire des matériels, logiciels et comptes, avec un responsable identifié.",
    "mfa": "Étendre l'authentification multifacteur aux comptes administrateurs et aux accès sensibles.",
    "backup": "Vérifier la fréquence des sauvegardes, leur isolement et réaliser une restauration de contrôle.",
    "updates": "Formaliser le suivi des correctifs de sécurité et les délais de traitement des mises à jour.",
    "endpoint": "Vérifier la couverture des protections sur les postes et serveurs et le suivi des alertes.",
    "access": "Organiser une revue périodique des droits et révoquer rapidement les accès obsolètes.",
    "network": "Faire revoir la segmentation des réseaux sensibles et les accès distants autorisés.",
    "training": "Planifier une sensibilisation régulière au phishing et aux signalements d'incidents.",
    "incident": "Documenter les contacts, responsabilités et premières étapes du plan de gestion d'incident.",
    "suppliers": "Identifier les prestataires critiques et vérifier leurs engagements contractuels de sécurité.",
}


def action_plan(answers):
    """Prioritize negative, partial and unknown declarations without claiming an audit."""
    checked = validate_answers(answers)
    order = {"NO": 0, "PARTIAL": 1, "UNKNOWN": 2}
    labels = {"NO": "Priorité haute déclarée", "PARTIAL": "À renforcer", "UNKNOWN": "À confirmer"}
    issues = []
    for key in QUESTIONS:
        answer = checked[key]
        if answer != "YES":
            issues.append({"domain": QUESTIONS[key],
                           "priority": labels[answer],
                           "recommendation": RECOMMENDATIONS[key],
                           "_order": order[answer]})
    issues.sort(key=lambda item: item["_order"])
    for issue in issues:
        issue.pop("_order")
    return issues


def roadmap(answers):
    """Indicative phased recommendations from declarations, never a verified audit."""
    checked = validate_answers(answers)
    steps = []
    for state in ("NO", "UNKNOWN", "PARTIAL"):
        for key in QUESTIONS:
            if checked[key] != state:
                continue
            period = "0–30 jours" if state != "PARTIAL" else "31–60 jours"
            action = RECOMMENDATIONS[key]
            if state == "UNKNOWN":
                action = "Confirmer la situation déclarée avec le client, puis : " + action
            steps.append({"period": period, "domain": QUESTIONS[key], "action": action})
    steps.append({"period": "61–90 jours", "domain": "Suivi",
                  "action": "Vérifier les mesures mises en œuvre, les preuves et les risques restant à traiter."})
    return steps
