"""Deterministic, sector-open diagnostic. It does not invent independent research.

No external AI request or unverified security scan is performed. All figures in
the financial scenarios are declared inputs or visibly labelled hypotheses.
"""
import json
import re
from decimal import Decimal, InvalidOperation

from .catalog import TRACKS, TIERS

GENERIC = [
    ("Pilotage", "Établir un tableau mensuel de ventes, coûts, trésorerie et satisfaction."),
    ("Clients", "Interroger les clients et mesurer les principales sources d'insatisfaction."),
    ("Processus", "Documenter les procédures récurrentes et les responsabilités."),
    ("Organisation", "Définir des objectifs et des responsables pour chaque chantier."),
    ("Finances", "Vérifier les marges, les prix et les charges sur pièces comptables."),
    ("Sécurité", "Contrôler les sauvegardes, les accès et les mises à jour autorisées."),
    ("Numérique", "Identifier les tâches répétitives automatisables avec validation."),
    ("Qualité", "Créer un indicateur de suivi des réclamations et délais."),
    ("Formation", "Définir les besoins de formation et la continuité d'activité."),
    ("Stratégie", "Fixer une feuille de route à 90 jours et vérifier les résultats."),
    ("Conformité", "Examiner les obligations propres au secteur avec un professionnel."),
    ("Résilience", "Préparer un plan de continuité et de gestion de crise."),
]
SECTOR_HINTS = (
    (("restaurant", "restauration", "traiteur", "snack", "boulangerie"),
     ("Coûts matière", "Contrôler fiches techniques, pertes et coûts matières.")),
    (("commerce", "boutique", "distribution", "magasin", "vente"),
     ("Stock", "Analyser rotation, ruptures, invendus et marge par famille.")),
    (("transport", "livraison", "logistique", "ambulanc", "taxi"),
     ("Flotte", "Mesurer immobilisations, entretien et coût par trajet.")),
    (("bâtiment", "construction", "chantier", "btp", "artisan"),
     ("Chantiers", "Mesurer les écarts devis, achats et temps passé.")),
    (("informatique", "logiciel", "télécom", "numérique"),
     ("Support", "Mesurer délais de résolution, tickets et incidents récurrents.")),
    (("santé", "clinique", "médical", "soin", "pharmacie"),
     ("Parcours patient", "Évaluer les délais et la confidentialité sans traiter de données médicales.")),
    (("association", "collectivité", "mairie", "public"),
     ("Gouvernance", "Clarifier objectifs, ressources et indicateurs d'intérêt général.")),
)
TRACK_ACTIONS = {
    "cyber": [
        ("Inventaire", "Inventorier équipements et comptes avec l'autorisation de l'entreprise."),
        ("Accès", "Examiner droits d'accès, MFA et désactivation des comptes sortants."),
        ("Sauvegardes", "Vérifier l'existence de sauvegardes et tester la restauration avec accord."),
        ("Incidents", "Rédiger les procédures d'alerte et de réponse aux incidents."),
    ],
    "digital": [
        ("Cartographie", "Cartographier logiciels, échanges de données et tâches manuelles."),
        ("Automatisation", "Choisir une automatisation pilote avec contrôle humain."),
        ("Interopérabilité", "Définir les interfaces et la gouvernance des données."),
    ],
    "operations": [
        ("Capacité", "Mesurer les délais, charges de travail et goulots d'étranglement."),
        ("Exécution", "Clarifier les rôles et automatiser les rappels de tâches."),
    ],
    "transformation": [
        ("Feuille de route", "Prioriser les projets par impact, faisabilité et risque."),
        ("Gouvernance", "Instaurer une revue mensuelle des objectifs et arbitrages."),
    ],
    "business": [
        ("Offre", "Comparer les besoins clients à l'offre actuelle."),
        ("Acquisition", "Mesurer les canaux commerciaux et leur coût."),
    ],
}


def clean_text(value, limit=1000):
    if not isinstance(value, str):
        raise ValueError("Texte attendu")
    value = re.sub(r"\s+", " ", value).strip()
    if not value or len(value) > limit:
        raise ValueError("Texte manquant ou trop long")
    return value


def _money(value):
    if value is None or value == "":
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Montant déclaré invalide") from exc
    if not amount.is_finite() or amount < 0 or amount > Decimal("1000000000000"):
        raise ValueError("Montant déclaré hors limites")
    return amount.quantize(Decimal("0.01"))


def parse_answers(value):
    if isinstance(value, str):
        if len(value) > 12000:
            raise ValueError("Questionnaire trop volumineux")
        try:
            value = json.loads(value)
        except (ValueError, TypeError) as exc:
            raise ValueError("Questionnaire JSON invalide") from exc
    if not isinstance(value, dict):
        raise ValueError("Questionnaire objet requis")
    allowed = ("activity", "challenges", "objective", "strengths", "tools", "cyber_practices",
               "employees", "revenue_eur", "costs_eur")
    if set(value) - set(allowed):
        raise ValueError("Champs non reconnus")
    result = {}
    for key in allowed[:6]:
        v = value.get(key) or ""
        if not isinstance(v, str) or len(v) > 2400:
            raise ValueError("Réponse textuelle invalide")
        result[key] = re.sub(r"\s+", " ", v).strip()
    employees = value.get("employees")
    if employees not in (None, ""):
        if isinstance(employees, bool) or not str(employees).isdigit() or int(employees) > 1000000:
            raise ValueError("Nombre de salariés invalide")
        result["employees"] = int(employees)
    else:
        result["employees"] = None
    for key in ("revenue_eur", "costs_eur"):
        amount = _money(value.get(key))
        result[key] = str(amount) if amount is not None else None
    if not result["objective"] or not result["challenges"]:
        raise ValueError("Objectif et difficultés obligatoires")
    return result


def financial_scenarios(answers):
    revenue = _money(answers.get("revenue_eur"))
    costs = _money(answers.get("costs_eur"))
    if revenue is None or costs is None:
        return None
    scenarios = []
    for label, annual in (("Prudent", Decimal("0")), ("Progressif", Decimal("0.05")),
                          ("Ambitieux", Decimal("0.12"))):
        projected_revenue = revenue * ((1 + annual) ** 3)
        # Costs assumed to grow by 3%/year regardless of revenue: hypothesis, NOT forecast.
        projected_costs = costs * (Decimal("1.03") ** 3)
        scenarios.append({
            "label": label, "hypothese_croissance_ca": str(annual * 100) + "%/an",
            "ca_annee_3": str(round(projected_revenue, 2)),
            "charges_annee_3": str(round(projected_costs, 2)),
            "resultat_simplifie_annee_3": str(round(projected_revenue - projected_costs, 2)),
        })
    return {"base_declaree": {"ca": str(revenue), "charges": str(costs)},
            "hypothese_couts": "+3%/an (illustration)", "scenarios": scenarios,
            "warning": "Scénarios illustratifs fondés uniquement sur les déclarations, sans étude comptable ni garantie."}


def build_assessment(company_name, sector, track, tier, answers):
    if track not in TRACKS or tier not in TIERS:
        raise ValueError("Offre inconnue")
    company_name = clean_text(company_name, 150)
    sector = clean_text(sector, 200)  # Any sector: keywords merely customize suggestions.
    answers = parse_answers(answers)
    items = []
    lower = (sector + " " + answers["activity"]).lower()
    for words, hint in SECTOR_HINTS:
        if any(word in lower for word in words):
            items.append(hint)
    items.extend(TRACK_ACTIONS[track])
    items.extend(GENERIC)
    count = {"basic": 5, "advanced": 8, "expert": 12}[tier]
    unique, seen = [], set()
    for title, description in items:
        if title not in seen and len(unique) < count:
            seen.add(title)
            unique.append({"id": len(unique) + 1, "theme": title, "action": description,
                           "status": "À faire", "horizon_jours": 30 if len(unique) < 4 else 90})
    coverage = sum(bool(answers.get(k)) for k in ("activity", "challenges", "objective",
                            "strengths", "tools", "cyber_practices", "employees",
                            "revenue_eur", "costs_eur"))
    return {
        "company_name": company_name, "sector": sector, "track": TRACKS[track],
        "tier": TIERS[tier], "objective_declared": answers["objective"],
        "challenges_declared": answers["challenges"],
        "strengths_declared": answers.get("strengths") or "Non renseignées",
        "data_completeness_pct": round(100 * coverage / 9),
        "data_completeness_label": "Complétude des données, pas une note de santé de l'entreprise",
        "actions": unique,
        "scenarios": financial_scenarios(answers) if tier != "basic" else None,
        "limitations": [
            "Analyse préliminaire fondée sur les seules réponses de l'entreprise.",
            "Aucun audit technique, comptable, juridique ou de conformité réalisé automatiquement.",
            "Actions proposées comme pistes à vérifier ; elles ne constatent pas un défaut avéré.",
            "Les spécificités réglementaires du secteur requièrent une validation spécialisée.",
        ],
    }
