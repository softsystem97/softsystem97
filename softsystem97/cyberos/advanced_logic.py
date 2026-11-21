"""Pure CyberOS V2 validation and executive statistics, no external monitoring."""
from .logic import choice, identifier, text

SCENARIOS = ("POWER", "INTERNET", "CYCLONE", "RANSOMWARE", "DATA_LOSS", "OTHER")
DRILLS = ("PHISHING", "RANSOMWARE", "OUTAGE", "DATA_LEAK", "OTHER")


def dependency_data(source, target, description):
    source, target = identifier(source), identifier(target)
    if source == target:
        raise ValueError("Une dépendance exige deux équipements distincts.")
    return {"source_asset": source, "target_asset": target,
            "description": text(description, 300, "Dépendance")}


def continuity_data(service, scenario, impact, fallback_steps, owner_role):
    return {
        "service": text(service, 120, "Service essentiel"),
        "scenario": choice(scenario, SCENARIOS, "Scénario"),
        "impact": choice(impact, ("LOW", "MEDIUM", "HIGH", "CRITICAL"), "Impact"),
        "fallback_steps": text(fallback_steps, 1600, "Consignes de repli"),
        "owner_role": text(owner_role, 100, "Responsable"),
    }


def drill_data(scenario, objectives):
    return {"scenario": choice(scenario, DRILLS, "Exercice"),
            "objectives": text(objectives, 1000, "Objectifs")}


def executive_summary(assets, actions, incidents, dependencies, plans, drills):
    """Counts of declared records, never a verified risk score or certification."""
    return {
        "inventoried_assets": len(assets),
        "high_criticality_assets": sum(a.get("criticality") in ("HIGH", "CRITICAL") for a in assets),
        "open_actions": sum(a.get("state") != "VERIFIED" for a in actions),
        "verified_actions": sum(a.get("state") == "VERIFIED" for a in actions),
        "open_incidents": sum(i.get("state") != "CLOSED" for i in incidents),
        "mapped_dependencies": len(dependencies),
        "continuity_plans": len(plans),
        "declared_exercises": len(drills),
        "warnings": ("Chiffres basés sur les dossiers enregistrés et non sur un audit du réseau.",
                     "La présence d'un plan ne prouve pas qu'il a été testé."),
    }
