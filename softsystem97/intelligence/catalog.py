"""Commercial catalog — prices and service scopes are server-controlled."""
from decimal import Decimal

TRACKS = {
    "business": "Stratégie et développement",
    "cyber": "Cybersécurité et résilience",
    "digital": "Transformation numérique",
    "operations": "Organisation et performance",
    "transformation": "Transformation 360",
}
TIERS = {"basic": "Basique", "advanced": "Avancé", "expert": "Expert"}
PRICES_EUR = {
    "business": {"basic": "149.00", "advanced": "499.00", "expert": "1490.00"},
    "cyber": {"basic": "129.00", "advanced": "399.00", "expert": "1490.00"},
    "digital": {"basic": "149.00", "advanced": "499.00", "expert": "1490.00"},
    "operations": {"basic": "149.00", "advanced": "499.00", "expert": "1490.00"},
    "transformation": {"basic": "149.00", "advanced": "499.00", "expert": "1490.00"},
}
SCOPE = {
    "basic": ["Diagnostic initial", "Forces et points d'attention déclarés", "5 actions prioritaires", "Rapport PDF"],
    "advanced": ["Diagnostic multidimensionnel", "Scénarios financiers indicatifs si données fournies",
                 "8 actions, priorités et calendrier", "Rapport PDF"],
    "expert": ["Étude stratégique approfondie", "Scénarios à 36 mois si données fournies",
               "12 actions et feuille de route", "Revue humaine avant remise du PDF"],
}
ALLOWED_STATES = ("À faire", "En cours", "Terminée")


def offer(track, tier):
    if track not in TRACKS or tier not in TIERS:
        raise ValueError("Formule ou spécialité inconnue")
    return {
        "track": track, "tier": tier, "title": TRACKS[track],
        "level": TIERS[tier], "price_eur": str(Decimal(PRICES_EUR[track][tier])),
        "currency": "EUR", "scope": SCOPE[tier],
    }


def catalog():
    return [offer(track, tier) for track in TRACKS for tier in TIERS]
