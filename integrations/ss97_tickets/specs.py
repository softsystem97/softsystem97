"""Spécifications métier — Module Tickets SS97 (cycle terrain complet)."""

from __future__ import annotations

DT_ISSUE = "Issue"
COMPANY = "SoftSystem97"

# Parcours officiel client → admin → technicien → clôture (canon + alias runtime)
# Les alias historiques restent acceptés pour ne pas casser les filtres / UI existants.
OFFICIAL_JOURNEY_STATUSES = [
    "Brouillon",
    "Nouveau",
    "En attente de validation",
    "Informations client manquantes",
    "En attente de paiement",
    "Paiement confirmé",
    "À affecter",
    "Affecté au technicien",
    "Notification technicien envoyée",
    "Accepté par le technicien",
    "Refusé par le technicien",
    "Rendez-vous planifié",
    "En attente du client",
    "Prêt à commencer",
    "Intervention en cours",
    "Intervention en pause",
    "Suspendu — risque sécurité",
    "Diagnostic en cours",
    "Autorisation distante demandée",
    "Autorisation distante accordée",
    "Autorisation distante refusée",
    "Session distante active",
    "Session distante terminée",
    "Solution appliquée",
    "Tests en cours",
    "Tests réussis",
    "Rapport en préparation",
    "Intervention terminée",
    "Validation client en attente",
    "Validé par le client",
    "Validation administrateur en attente",
    "Réouvert",
    "Clôturé",
    "Annulé",
]

# Alias runtime → statut officiel (lecture / normalisation)
STATUS_ALIAS_TO_OFFICIAL = {
    "Analyse IA en cours": "En attente de validation",
    "Analyse terminée": "En attente de validation",
    "Ticket prêt pour validation": "En attente de validation",
    "Validé": "En attente de validation",
    "Ouvert": "Nouveau",
    "Paiement requis": "En attente de paiement",
    "Payé": "Paiement confirmé",
    "Technicien recherché": "À affecter",
    "En attente d'attribution": "À affecter",
    "Affecté": "Affecté au technicien",
    "Attribué": "Affecté au technicien",
    "Technicien affecté": "Affecté au technicien",
    "Accepté": "Accepté par le technicien",
    "Intervention planifiée": "Rendez-vous planifié",
    "En cours": "Intervention en cours",
    "En pause": "Intervention en pause",
    "Repris": "Intervention en cours",
    "En attente client": "En attente du client",
    "En attente d'un document": "En attente du client",
    "En attente document": "En attente du client",
    "En attente": "En attente du client",
    "Résolu": "Intervention terminée",
    "Terminé": "Intervention terminée",
    "Rapport soumis": "Rapport en préparation",
    "Rapport disponible": "Validation client en attente",
    "Ticket clôturé": "Clôturé",
    "Fermé": "Clôturé",
    "Archivé": "Clôturé",
    "Rouvert": "Réouvert",
    "Devis nécessaire": "En attente de paiement",
}

TICKET_STATUSES = [
    # —— Canon officiel ——
    *OFFICIAL_JOURNEY_STATUSES,
    # —— Alias / étapes runtime existantes (compatibilité) ——
    "Analyse IA en cours",
    "Analyse terminée",
    "Ticket prêt pour validation",
    "Validé",
    "Ouvert",
    "Paiement requis",
    "Payé",
    "Technicien recherché",
    "En attente d'attribution",
    "Affecté",
    "Attribué",
    "Technicien affecté",
    "Accepté",
    "Intervention planifiée",
    "En déplacement",
    "En cours",
    "En pause",
    "Repris",
    "En attente client",
    "En attente d'un document",
    "En attente document",
    "En attente",
    "Résolu",
    "Terminé",
    "Rapport soumis",
    "Rapport disponible",
    "Ticket clôturé",
    "Fermé",
    "Archivé",
    "Rouvert",
    "Devis nécessaire",
]


def _dedupe_statuses(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for s in items:
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


TICKET_STATUSES = _dedupe_statuses(TICKET_STATUSES)

STATUS_TO_NATIVE = {
    "Brouillon": "Open",
    "Nouveau": "Open",
    "En attente de validation": "Open",
    "Informations client manquantes": "On Hold",
    "En attente de paiement": "Open",
    "Paiement confirmé": "Open",
    "À affecter": "Open",
    "Affecté au technicien": "Open",
    "Notification technicien envoyée": "Open",
    "Accepté par le technicien": "Open",
    "Refusé par le technicien": "Open",
    "Rendez-vous planifié": "Open",
    "En attente du client": "On Hold",
    "Prêt à commencer": "Open",
    "Intervention en cours": "Open",
    "Intervention en pause": "On Hold",
    "Diagnostic en cours": "Open",
    "Autorisation distante demandée": "On Hold",
    "Autorisation distante accordée": "Open",
    "Autorisation distante refusée": "On Hold",
    "Session distante active": "Open",
    "Session distante terminée": "Open",
    "Solution appliquée": "Open",
    "Tests en cours": "Open",
    "Tests réussis": "Open",
    "Rapport en préparation": "Resolved",
    "Intervention terminée": "Resolved",
    "Validation client en attente": "Resolved",
    "Validé par le client": "Resolved",
    "Validation administrateur en attente": "Resolved",
    "Réouvert": "Open",
    "Clôturé": "Closed",
    "Annulé": "Closed",
    # Alias runtime
    "Analyse IA en cours": "Open",
    "Analyse terminée": "Open",
    "Ticket prêt pour validation": "Open",
    "Validé": "Open",
    "Ouvert": "Open",
    "Paiement requis": "Open",
    "Payé": "Open",
    "Technicien recherché": "Open",
    "En attente d'attribution": "Open",
    "Affecté": "Open",
    "Attribué": "Open",
    "Technicien affecté": "Open",
    "Accepté": "Open",
    "Intervention planifiée": "Open",
    "En déplacement": "Open",
    "En cours": "Open",
    "En pause": "On Hold",
    "Repris": "Open",
    "En attente client": "On Hold",
    "En attente d'un document": "On Hold",
    "En attente document": "On Hold",
    "En attente": "On Hold",
    "Résolu": "Resolved",
    "Terminé": "Closed",
    "Rapport soumis": "Resolved",
    "Rapport disponible": "Resolved",
    "Ticket clôturé": "Closed",
    "Fermé": "Closed",
    "Archivé": "Closed",
    "Rouvert": "Open",
    "Devis nécessaire": "Open",
}

LEGACY_STATUS_MAP = {
    **STATUS_ALIAS_TO_OFFICIAL,
    "Ticket créé": "Nouveau",
}

STATUS_ACTIONS: dict[str, list[tuple[str, str]]] = {
    "Nouveau": [
        ("Ouvrir", "Ouvert"),
        ("Attribuer", "Affecté"),
        ("File d'attente", "En attente d'attribution"),
        ("Prendre en charge", "Accepté"),
    ],
    "Analyse IA en cours": [
        ("Valider", "Validé"),
        ("Ouvrir", "Ouvert"),
        ("File d'attente", "En attente d'attribution"),
    ],
    "Analyse terminée": [
        ("Valider", "Validé"),
        ("Demander paiement", "Paiement requis"),
        ("Ouvrir", "Ouvert"),
        ("File d'attente", "En attente d'attribution"),
    ],
    "Ticket prêt pour validation": [
        ("Valider", "Validé"),
        ("Demander paiement", "Paiement requis"),
        ("Ouvrir", "Ouvert"),
    ],
    "Paiement confirmé": [
        ("Rechercher technicien", "Technicien recherché"),
        ("File d'attente", "En attente d'attribution"),
    ],
    "Technicien recherché": [
        ("Attribuer", "Affecté"),
        ("File d'attente", "En attente d'attribution"),
        ("Prendre en charge", "Accepté"),
    ],
    "Ouvert": [
        ("Attribuer", "Affecté"),
        ("File d'attente", "En attente d'attribution"),
        ("Prendre en charge", "Accepté"),
    ],
    "En attente d'attribution": [
        ("Attribuer", "Affecté"),
        ("Prendre en charge", "Accepté"),
    ],
    "Affecté": [
        ("Accepter", "Technicien affecté"),
        ("Accepté technicien", "Accepté par le technicien"),
        ("Mettre en attente", "En attente"),
    ],
    "Attribué": [
        ("Accepter", "Technicien affecté"),
        ("Accepté technicien", "Accepté par le technicien"),
        ("Mettre en attente", "En attente"),
    ],
    "Technicien affecté": [
        ("Diagnostic", "Diagnostic en cours"),
        ("Planifier intervention", "Intervention planifiée"),
        ("Démarrer intervention", "En cours"),
        ("Mettre en pause", "En pause"),
    ],
    "En pause": [
        ("Reprendre", "Repris"),
        ("Terminer", "Terminé"),
    ],
    "Repris": [
        ("Mettre en pause", "En pause"),
        ("Terminer", "Terminé"),
        ("Résoudre", "Résolu"),
    ],
    "Accepté": [
        ("Diagnostic", "Diagnostic en cours"),
        ("Planifier intervention", "Intervention planifiée"),
        ("Partir en déplacement", "En déplacement"),
        ("Démarrer intervention", "En cours"),
        ("Mettre en pause", "En pause"),
    ],
    "Accepté par le technicien": [
        ("Diagnostic", "Diagnostic en cours"),
        ("Planifier intervention", "Intervention planifiée"),
        ("Démarrer intervention", "Intervention en cours"),
    ],
    "Diagnostic en cours": [
        ("Planifier intervention", "Intervention planifiée"),
        ("Démarrer intervention", "Intervention en cours"),
        ("Demander info client", "En attente du client"),
        ("Demander document", "En attente d'un document"),
    ],
    "Intervention planifiée": [
        ("Partir en déplacement", "En déplacement"),
        ("Démarrer intervention", "Intervention en cours"),
        ("Demander info client", "En attente du client"),
    ],
    "En déplacement": [
        ("Arriver / démarrer", "Intervention en cours"),
        ("Mettre en attente", "En attente"),
    ],
    "Intervention en cours": [
        ("Demander info client", "En attente du client"),
        ("Demander document", "En attente d'un document"),
        ("Marquer résolu", "Résolu"),
    ],
    "En cours": [
        ("Demander info client", "En attente du client"),
        ("Demander document", "En attente d'un document"),
        ("Marquer résolu", "Résolu"),
    ],
    "En attente du client": [
        ("Reprendre", "Intervention en cours"),
        ("Marquer résolu", "Résolu"),
    ],
    "En attente d'un document": [
        ("Reprendre", "Intervention en cours"),
        ("Marquer résolu", "Résolu"),
    ],
    "En attente": [
        ("Reprendre", "En cours"),
        ("Reprendre déplacement", "En déplacement"),
        ("Marquer résolu", "Résolu"),
    ],
    "Résolu": [
        ("Soumettre rapport", "Rapport soumis"),
        ("Terminer", "Terminé"),
        ("Fermer", "Fermé"),
        ("Validation client", "Terminé"),
        ("Réouvrir", "Rouvert"),
    ],
    "Rapport soumis": [
        ("Clôturer ticket", "Ticket clôturé"),
        ("Rapport disponible", "Rapport disponible"),
        ("Terminer", "Terminé"),
        ("Archiver", "Archivé"),
    ],
    "Ticket clôturé": [
        ("Archiver", "Archivé"),
        ("Réouvrir", "Rouvert"),
    ],
    "Terminé": [
        ("Fermer", "Fermé"),
        ("Clôturer ticket", "Ticket clôturé"),
        ("Archiver", "Archivé"),
        ("Réouvrir", "Rouvert"),
    ],
    "Fermé": [
        ("Archiver", "Archivé"),
        ("Réouvrir", "Rouvert"),
    ],
    "Archivé": [
        ("Réouvrir", "Rouvert"),
    ],
    "Rouvert": [
        ("Attribuer", "Affecté"),
        ("Prendre en charge", "Accepté"),
        ("Diagnostic", "Diagnostic en cours"),
        ("Démarrer intervention", "Intervention en cours"),
    ],
    "Réouvert": [
        ("Attribuer", "Affecté au technicien"),
        ("Prendre en charge", "Accepté par le technicien"),
        ("Diagnostic", "Diagnostic en cours"),
        ("Démarrer intervention", "Intervention en cours"),
    ],
    "Affecté au technicien": [
        ("Notifier technicien", "Notification technicien envoyée"),
        ("Accepter", "Accepté par le technicien"),
        ("Refuser", "Refusé par le technicien"),
    ],
    "Notification technicien envoyée": [
        ("Accepter", "Accepté par le technicien"),
        ("Refuser", "Refusé par le technicien"),
    ],
    "Refusé par le technicien": [
        ("Réaffecter", "À affecter"),
    ],
    "À affecter": [
        ("Affecter", "Affecté au technicien"),
    ],
    "Prêt à commencer": [
        ("Commencer", "Intervention en cours"),
        ("Mettre en pause", "Intervention en pause"),
    ],
    "Intervention en pause": [
        ("Reprendre", "Intervention en cours"),
        ("Attente client", "En attente du client"),
    ],
    "Autorisation distante demandée": [
        ("Accorder", "Autorisation distante accordée"),
        ("Refuser", "Autorisation distante refusée"),
    ],
    "Autorisation distante accordée": [
        ("Ouvrir session", "Session distante active"),
    ],
    "Session distante active": [
        ("Terminer session", "Session distante terminée"),
        ("Solution", "Solution appliquée"),
    ],
    "Session distante terminée": [
        ("Solution", "Solution appliquée"),
        ("Rapport", "Rapport en préparation"),
    ],
    "Solution appliquée": [
        ("Tests", "Tests en cours"),
    ],
    "Tests en cours": [
        ("Tests OK", "Tests réussis"),
    ],
    "Tests réussis": [
        ("Rapport", "Rapport en préparation"),
        ("Terminer", "Intervention terminée"),
    ],
    "Rapport en préparation": [
        ("Terminer", "Intervention terminée"),
    ],
    "Intervention terminée": [
        ("Demander validation", "Validation client en attente"),
    ],
    "Validation client en attente": [
        ("Valider client", "Validé par le client"),
        ("Réouvrir", "Réouvert"),
    ],
    "Validé par le client": [
        ("Clôturer", "Clôturé"),
    ],
    "Clôturé": [
        ("Réouvrir", "Réouvert"),
        ("Annuler", "Annulé"),
    ],
    "Informations client manquantes": [
        ("Infos reçues", "En attente de validation"),
    ],
    "Brouillon": [
        ("Soumettre", "Nouveau"),
        ("Annuler", "Annulé"),
    ],
    "Annulé": [],
    "En attente client": [
        ("Reprendre", "Intervention en cours"),
        ("Marquer résolu", "Résolu"),
    ],
    "En attente document": [
        ("Reprendre", "Intervention en cours"),
        ("Marquer résolu", "Résolu"),
    ],
}

PRIORITY_MAP = {
    # FR → Issue Priority (ERPNext Link)
    "Faible": "Low",
    "Basse": "Low",
    "Standard": "Low",
    "Normal": "Medium",
    "Normale": "Medium",
    "Prioritaire": "Medium",
    "Haute": "High",
    "Élevée": "High",
    "Elevee": "High",
    "Urgente": "Urgent",
    "Critique": "Urgent",
    "Critical": "Urgent",
    # EN passthrough (canonique)
    "Low": "Low",
    "Medium": "Medium",
    "High": "High",
    "Urgent": "Urgent",
}

ISSUE_CATEGORIES = [
    "Assistance informatique",
    "Maintenance",
    "Microsoft 365",
    "Cybersécurité",
    "Réseau",
    "Cloud",
    "Matériel",
    "Logiciel",
    "Autre",
]

CUSTOM_FIELDS = [
    (
        "ss97_ticket_status",
        "Statut ticket SS97",
        "Select",
        "\n".join(TICKET_STATUSES),
        "priority",
    ),
    (
        "ss97_category",
        "Catégorie",
        "Select",
        "\n".join(ISSUE_CATEGORIES),
        "ss97_ticket_status",
    ),
    ("ss97_first_name", "Prénom contact", "Data", None, "ss97_category"),
    ("ss97_last_name", "Nom contact", "Data", None, "ss97_first_name"),
    ("ss97_contact_email", "Email contact", "Data", None, "ss97_last_name"),
    ("ss97_contact_phone", "Téléphone contact", "Data", None, "ss97_contact_email"),
    ("ss97_country", "Pays", "Data", None, "ss97_contact_phone"),
    (
        "ss97_language",
        "Langue",
        "Select",
        "Français\nEnglish\nEspañol\nAutre",
        "ss97_country",
    ),
    ("ss97_terms_accepted", "CGU acceptées", "Check", None, "ss97_language"),
    ("ss97_technician", "Technicien affecté", "Link", "User", "ss97_terms_accepted"),
    ("ss97_assigned_on", "Affecté le", "Datetime", None, "ss97_technician"),
    ("ss97_accepted_on", "Accepté le", "Datetime", None, "ss97_assigned_on"),
    (
        "ss97_en_route_on",
        "Déplacement démarré le",
        "Datetime",
        None,
        "ss97_accepted_on",
    ),
    (
        "ss97_intervention_started_on",
        "Intervention démarrée le",
        "Datetime",
        None,
        "ss97_en_route_on",
    ),
    ("ss97_resolved_on", "Résolu le", "Datetime", None, "ss97_intervention_started_on"),
    ("ss97_closed_on", "Fermé / terminé le", "Datetime", None, "ss97_resolved_on"),
    ("ss97_archived_on", "Archivé le", "Datetime", None, "ss97_closed_on"),
    ("ss97_sla_deadline", "Échéance SLA", "Datetime", None, "ss97_archived_on"),
    ("ss97_public_ref", "Référence publique", "Data", None, "ss97_sla_deadline"),
    (
        "ss97_source",
        "Source",
        "Select",
        "Portail\nDesk\nEmail\nTéléphone\nJira\nServiceNow",
        "ss97_public_ref",
    ),
    # Intervention terrain
    ("ss97_client_name", "Client / entreprise", "Data", None, "ss97_source"),
    (
        "ss97_device_summary",
        "Appareil / équipement",
        "Small Text",
        None,
        "ss97_client_name",
    ),
    (
        "ss97_intervention_address",
        "Adresse intervention",
        "Small Text",
        None,
        "ss97_device_summary",
    ),
    (
        "ss97_intervention_contact",
        "Disponibilité / contact préféré",
        "Data",
        None,
        "ss97_intervention_address",
    ),
    (
        "ss97_intervention_priority",
        "Priorité terrain",
        "Select",
        "Standard\nPrioritaire\nUrgent\nCritique",
        "ss97_intervention_contact",
    ),
    (
        "ss97_planned_duration_min",
        "Durée prévue (min)",
        "Int",
        None,
        "ss97_intervention_priority",
    ),
    (
        "ss97_actual_duration_min",
        "Durée réelle (min)",
        "Int",
        None,
        "ss97_planned_duration_min",
    ),
    (
        "ss97_intervention_photos",
        "Photos intervention",
        "Attach",
        None,
        "ss97_actual_duration_min",
    ),
    (
        "ss97_intervention_docs",
        "Documents intervention",
        "Attach",
        None,
        "ss97_intervention_photos",
    ),
    (
        "ss97_client_signature",
        "Signature client",
        "Attach Image",
        None,
        "ss97_intervention_docs",
    ),
    (
        "ss97_intervention_report",
        "Rapport d'intervention",
        "Text Editor",
        None,
        "ss97_client_signature",
    ),
    ("ss97_geo_lat", "GPS latitude", "Float", None, "ss97_intervention_report"),
    ("ss97_geo_lng", "GPS longitude", "Float", None, "ss97_geo_lat"),
    ("ss97_geo_accuracy", "GPS précision (m)", "Float", None, "ss97_geo_lng"),
    ("ss97_geo_captured_on", "GPS capturé le", "Datetime", None, "ss97_geo_accuracy"),
    # Paiement ticket (espace client / Ticket Libre)
    (
        "ss97_invoice_amount",
        "Montant facture SS97",
        "Currency",
        None,
        "ss97_geo_captured_on",
    ),
    (
        "ss97_payment_status",
        "Statut paiement SS97",
        "Data",
        None,
        "ss97_invoice_amount",
    ),
    (
        "ss97_payment_ref",
        "Référence paiement SS97",
        "Data",
        None,
        "ss97_payment_status",
    ),
]

ROLES = [
    ("SS97 Support", "Équipe support Help Desk"),
    ("SS97 Technician", "Technicien terrain"),
    ("SS97 Admin ITSM", "Administrateur — supervision ITSM complète"),
    ("SS97 Support Manager", "Responsable Support — pilotage tickets / SLA"),
    ("SS97 Commercial", "Commercial — clients / devis / contrats"),
    ("SS97 Comptabilite", "Comptabilité — factures / CA interventions"),
]

# Cartes Help Desk de base
DASHBOARD_CARDS = [
    ("SS97 HD - Total tickets", "[]"),
    ("SS97 HD - Nouveaux", '[["Issue","ss97_ticket_status","=","Nouveau"]]'),
    (
        "SS97 HD - Affectés",
        '[["Issue","ss97_ticket_status","in",["Affecté","Attribué"]]]',
    ),
    ("SS97 HD - Acceptés", '[["Issue","ss97_ticket_status","=","Accepté"]]'),
    (
        "SS97 HD - En déplacement",
        '[["Issue","ss97_ticket_status","=","En déplacement"]]',
    ),
    ("SS97 HD - En cours", '[["Issue","ss97_ticket_status","=","En cours"]]'),
    ("SS97 HD - En attente", '[["Issue","ss97_ticket_status","=","En attente"]]'),
    ("SS97 HD - Résolus", '[["Issue","ss97_ticket_status","=","Résolu"]]'),
    ("SS97 HD - Terminés", '[["Issue","ss97_ticket_status","in",["Terminé","Fermé"]]]'),
    ("SS97 HD - Archivés", '[["Issue","ss97_ticket_status","=","Archivé"]]'),
    ("SS97 HD - Urgents", '[["Issue","priority","in",["High","Urgent"]]]'),
]

# Cartes supplémentaires — Centre de supervision Admin ITSM
ADMIN_DASHBOARD_CARDS = DASHBOARD_CARDS + [
    (
        "SS97 HD - Fermés",
        '[["Issue","ss97_ticket_status","in",["Fermé","Terminé","Archivé"]]]',
    ),
    (
        "SS97 HD - En attente attribution",
        '[["Issue","ss97_ticket_status","=","En attente d\'attribution"]]',
    ),
    (
        "SS97 HD - Ouverts",
        '[["Issue","ss97_ticket_status","in",["Nouveau","Ouvert","Affecté","Attribué","Accepté","En cours","En attente"]]]',
    ),
    (
        "SS97 HD - SLA dépassé",
        '[["Issue","ss97_sla_deadline","is","set"],["Issue","ss97_sla_deadline","<","Today"],["Issue","ss97_ticket_status","not in",["Fermé","Archivé","Résolu","Terminé"]]]',
    ),
    ("SS97 HD - Interventions du jour", '[["Issue","creation",">=","Today"]]'),
    (
        "SS97 HD - Non attribués",
        '[["Issue","ss97_technician","is","not set"],["Issue","ss97_ticket_status","not in",["Fermé","Archivé","Résolu","Terminé"]]]',
    ),
    (
        "SS97 HD - Alertes critiques",
        '[["Issue","priority","=","Urgent"],["Issue","ss97_ticket_status","not in",["Fermé","Archivé","Résolu","Terminé"]]]',
    ),
    ("SS97 ITSM - Réception", '[["Issue","ss97_itsm_stage","=","1. Réception"]]'),
    (
        "SS97 ITSM - Qualification",
        '[["Issue","ss97_itsm_stage","=","2. Qualification"]]',
    ),
    ("SS97 ITSM - Affectation", '[["Issue","ss97_itsm_stage","=","3. Affectation"]]'),
    ("SS97 ITSM - Traitement", '[["Issue","ss97_itsm_stage","=","4. Traitement"]]'),
    ("SS97 ITSM - Résolution", '[["Issue","ss97_itsm_stage","=","5. Résolution"]]'),
    ("SS97 ITSM - Clôture", '[["Issue","ss97_itsm_stage","=","6. Clôture"]]'),
]

SLA_HOURS = {
    "Low": 72,
    "Medium": 24,
    "High": 8,
    "Urgent": 2,
}
