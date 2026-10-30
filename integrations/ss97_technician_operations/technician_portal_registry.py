"""Recovered Web Page registry. Listing routes never imports missing page modules."""

from importlib import import_module


def _lazy(module, symbol, *args, portals_argument=False):
    def build():
        builder = getattr(import_module(module), symbol)
        if portals_argument:
            return builder(
                import_module("integrations.ss97_technician_operations.portals")
            )
        return builder(*args)

    return build


def deploy_specs():
    """Return the original route/builders; no fallback or automatic deployment."""
    return [
        (
            "Connexion espace technicien SS97",
            "espace-technicien/login",
            _lazy(
                "integrations.ss97_technician_operations.technician_login_page",
                "page_technician_login",
            ),
        ),
        (
            "Portail Technicien SoftSystem97",
            "espace-technicien/dashboard",
            _lazy(
                "integrations.ss97_technician_operations.portals",
                "page_technician_dashboard",
            ),
        ),
        (
            "Tableau de bord technicien SS97",
            "espace-technicien/tableau-de-bord",
            _lazy(
                "integrations.ss97_technician_operations.portals",
                "page_technician_dashboard",
            ),
        ),
        (
            "Profil technicien SS97",
            "espace-technicien/profil",
            _lazy(
                "integrations.ss97_technician_workspace.pages", "page_tech_profil_full"
            ),
        ),
        (
            "Disponibilités technicien SS97",
            "espace-technicien/disponibilites",
            _lazy("integrations.ss97_tech_portal_full.pages_hub", "page_disponibilite"),
        ),
        (
            "Missions technicien SS97",
            "espace-technicien/missions",
            _lazy(
                "integrations.ss97_technician_operations.portals", "page_tech_missions"
            ),
        ),
        (
            "Interventions technicien SS97",
            "espace-technicien/interventions",
            _lazy(
                "integrations.ss97_technician_etape6.deploy",
                "page_tickets",
                portals_argument=True,
            ),
        ),
        (
            "Rapports technicien SS97",
            "espace-technicien/rapports",
            _lazy(
                "integrations.ss97_technician_operations.stabilize_modules",
                "page_rapports",
            ),
        ),
        (
            "Documents technicien SS97",
            "espace-technicien/documents",
            _lazy(
                "integrations.ss97_technician_workspace.pages", "page_tech_docs_full"
            ),
        ),
        (
            "Notifications technicien SS97",
            "espace-technicien/notifications",
            _lazy(
                "integrations.ss97_technician_operations.cockpit_intervention",
                "page_notifications_tech",
            ),
        ),
        (
            "Formations technicien SS97",
            "espace-technicien/formations",
            _lazy("integrations.ss97_technician_quality.pages", "page_tech_formations"),
        ),
        (
            "Examens technicien SS97",
            "espace-technicien/examens",
            _lazy(
                "integrations.ss97_technician_quality.pages", "page_technician_exams"
            ),
        ),
        (
            "Compétences technicien SS97",
            "espace-technicien/competences",
            _lazy("integrations.ss97_tech_portal_full.pages_hub", "page_competences"),
        ),
        (
            "Certifications technicien SS97",
            "espace-technicien/certifications",
            _lazy(
                "integrations.ss97_technician_quality.pages", "page_tech_certifications"
            ),
        ),
        (
            "Évaluations technicien SS97",
            "espace-technicien/evaluations",
            _lazy("integrations.ss97_tech_portal_full.pages_hub", "page_evaluations"),
        ),
        (
            "Performance technicien SS97",
            "espace-technicien/performance",
            _lazy("integrations.ss97_tech_portal_full.pages_hub", "page_evaluations"),
        ),
        (
            "Base connaissances technicien SS97",
            "espace-technicien/base-connaissances",
            _lazy("integrations.ss97_technician_quality.pages", "page_tech_kb"),
        ),
        (
            "Matériel technicien SS97",
            "espace-technicien/materiel",
            _lazy("integrations.ss97_tech_portal_full.pages_hub", "page_materiel"),
        ),
        (
            "Logiciels technicien SS97",
            "espace-technicien/logiciels",
            _lazy("integrations.ss97_technician_quality.pages", "page_tech_licences"),
        ),
        (
            "Licences technicien SS97",
            "espace-technicien/licences",
            _lazy("integrations.ss97_technician_quality.pages", "page_tech_licences"),
        ),
        (
            "Commissions technicien SS97",
            "espace-technicien/commissions",
            _lazy(
                "integrations.ss97_technician_quality.pages", "page_tech_commissions"
            ),
        ),
        (
            "Maintenance technicien SS97",
            "espace-technicien/maintenance-preventive",
            _lazy(
                "integrations.ss97_technician_quality.pages", "page_tech_maintenance"
            ),
        ),
        (
            "Contrôle qualité technicien SS97",
            "espace-technicien/controle-qualite",
            _lazy("integrations.ss97_technician_quality.pages", "page_tech_quality"),
        ),
        (
            "Alertes prospects technicien SS97",
            "espace-technicien/alertes-prospects",
            _lazy(
                "integrations.ss97_prospect_alerts.pages",
                "page_technician_alerts",
                "alertes",
            ),
        ),
        (
            "Assistance technicien SS97",
            "espace-technicien/assistance",
            _lazy(
                "integrations.ss97_technician_operations.comms_security",
                "page_messages_center",
            ),
        ),
        (
            "Paramètres technicien SS97",
            "espace-technicien/parametres",
            _lazy("integrations.ss97_technician_workspace.pages", "page_tech_settings"),
        ),
        (
            "Mes tickets technicien",
            "espace-technicien/tickets",
            _lazy(
                "integrations.ss97_technician_etape6.deploy",
                "page_tickets",
                portals_argument=True,
            ),
        ),
        (
            "Profil technicien (legacy)",
            "technicien/informations",
            _lazy("integrations.ss97_tech_portal_full.pages_hub", "page_informations"),
        ),
        (
            "Disponibilité technicien (legacy)",
            "technicien/disponibilite",
            _lazy("integrations.ss97_tech_portal_full.pages_hub", "page_disponibilite"),
        ),
        (
            "Missions technicien (legacy)",
            "ss97-tech-missions",
            _lazy(
                "integrations.ss97_technician_operations.portals", "page_tech_missions"
            ),
        ),
    ]
