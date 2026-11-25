"""Migration portable du cockpit N2.
Ne configure aucun paiement, utilisateur ou droit.
N'active aucune fonctionnalite commerciale.
"""

import frappe

FIELDS = [{'fieldname': 'ss97_accepted_on',
  'label': 'Intervention acceptee le',
  'fieldtype': 'Datetime',
  'options': None,
  'default': None,
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_action_log',
  'label': 'Journal des actions',
  'fieldtype': 'Long Text',
  'options': None,
  'default': None,
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_actual_duration_min',
  'label': 'actual duration min',
  'fieldtype': 'Int',
  'options': None,
  'default': '0',
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_checklist_close_done',
  'label': 'checklist close done',
  'fieldtype': 'Check',
  'options': None,
  'default': '0',
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_checklist_pre_done',
  'label': 'Checklist avant intervention',
  'fieldtype': 'Check',
  'options': None,
  'default': '0',
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_client_message',
  'label': 'Message de suivi client',
  'fieldtype': 'Small Text',
  'options': None,
  'default': None,
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_closed_on',
  'label': 'closed on',
  'fieldtype': 'Datetime',
  'options': None,
  'default': None,
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_diagnostic',
  'label': 'diagnostic',
  'fieldtype': 'Long Text',
  'options': None,
  'default': None,
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_intervention_report',
  'label': 'intervention report',
  'fieldtype': 'Text Editor',
  'options': None,
  'default': None,
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_intervention_started_on',
  'label': 'Intervention demarree le',
  'fieldtype': 'Datetime',
  'options': None,
  'default': None,
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_pause_seconds',
  'label': 'Temps de pause en secondes',
  'fieldtype': 'Int',
  'options': None,
  'default': '0',
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_pause_started_on',
  'label': 'Pause commencee le',
  'fieldtype': 'Datetime',
  'options': None,
  'default': None,
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_proof_log',
  'label': 'Journal des preuves',
  'fieldtype': 'Long Text',
  'options': None,
  'default': None,
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_remote_session_active',
  'label': 'remote session active',
  'fieldtype': 'Check',
  'options': None,
  'default': '0',
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_resolved_by',
  'label': 'resolved by',
  'fieldtype': 'Link',
  'options': 'User',
  'default': None,
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_resolved_on',
  'label': 'resolved on',
  'fieldtype': 'Datetime',
  'options': None,
  'default': None,
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_security_suspend',
  'label': 'Suspension securite',
  'fieldtype': 'Check',
  'options': None,
  'default': '1',
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_status_transition_log',
  'label': 'Historique des statuts',
  'fieldtype': 'Long Text',
  'options': None,
  'default': None,
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_ticket_status',
  'label': 'Statut ticket SS97',
  'fieldtype': 'Select',
  'options': 'Brouillon\n'
             'Nouveau\n'
             'En attente de validation\n'
             'Informations client manquantes\n'
             'En attente de paiement\n'
             'Paiement confirmé\n'
             'À affecter\n'
             'Affecté au technicien\n'
             'Notification technicien envoyée\n'
             'Accepté par le technicien\n'
             'Refusé par le technicien\n'
             'Rendez-vous planifié\n'
             'En attente du client\n'
             'Prêt à commencer\n'
             'Intervention en cours\n'
             'Intervention en pause\n'
             'Suspendu — risque sécurité\n'
             'Diagnostic en cours\n'
             'Autorisation distante demandée\n'
             'Autorisation distante accordée\n'
             'Autorisation distante refusée\n'
             'Session distante active\n'
             'Session distante terminée\n'
             'Solution appliquée\n'
             'Tests en cours\n'
             'Tests réussis\n'
             'Rapport en préparation\n'
             'Intervention terminée\n'
             'Validation client en attente\n'
             'Validé par le client\n'
             'Validation administrateur en attente\n'
             'Réouvert\n'
             'Clôturé\n'
             'Annulé\n'
             'Analyse IA en cours\n'
             'Analyse terminée\n'
             'Ticket prêt pour validation\n'
             'Validé\n'
             'Ouvert\n'
             'Paiement requis\n'
             'Payé\n'
             'Technicien recherché\n'
             "En attente d'attribution\n"
             'Affecté\n'
             'Attribué\n'
             'Technicien affecté\n'
             'Accepté\n'
             'Intervention planifiée\n'
             'En déplacement\n'
             'En cours\n'
             'En pause\n'
             'Repris\n'
             'En attente client\n'
             "En attente d'un document\n"
             'En attente document\n'
             'En attente\n'
             'Résolu\n'
             'Terminé\n'
             'Rapport soumis\n'
             'Rapport disponible\n'
             'Ticket clôturé\n'
             'Fermé\n'
             'Archivé\n'
             'Rouvert\n'
             'Devis nécessaire',
  'default': None,
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_timer_resumed_on',
  'label': 'Chronometre repris le',
  'fieldtype': 'Datetime',
  'options': None,
  'default': None,
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_timer_status',
  'label': 'Etat du chronometre',
  'fieldtype': 'Select',
  'options': '\nrunning\npaused\nstopped',
  'default': 'stopped',
  'read_only': 1,
  'no_copy': 1},
 {'fieldname': 'ss97_work_seconds',
  'label': 'Temps de travail en secondes',
  'fieldtype': 'Int',
  'options': None,
  'default': '0',
  'read_only': 1,
  'no_copy': 1}]


def preflight():

    meta = frappe.get_meta("Issue")

    conflicts = []
    missing = []

    technician = meta.get_field("ss97_technician")

    if (
        not technician
        or technician.fieldtype != "Link"
        or technician.options != "User"
    ):
        conflicts.append("ss97_technician incompatible")

    for spec in FIELDS:

        name = spec["fieldname"]
        field = meta.get_field(name)

        if not field:
            missing.append(name)
            continue

        if field.fieldtype != spec["fieldtype"]:

            conflicts.append(name + ": type incompatible")
            continue

        if field.fieldtype == "Link":

            if field.options != spec["options"]:
                conflicts.append(name + ": lien incompatible")

        if field.fieldtype == "Select":

            expected = set(
                (spec["options"] or "").splitlines()
            )

            existing = set(
                (field.options or "").splitlines()
            )

            if not expected.issubset(existing):
                conflicts.append(name + ": options incompatibles")

        if not field.read_only:
            conflicts.append(name + ": champ modifiable")

        if name == "ss97_security_suspend":

            if str(field.default) != "1":
                conflicts.append(name + ": defaut non securise")

    return {
        "conflicts": conflicts,
        "missing": missing
    }


def execute():

    result = preflight()

    if result["conflicts"]:

        frappe.throw(
            "Migration cockpit bloquee : "
            + "; ".join(result["conflicts"])
        )

    missing = set(result["missing"])

    created = 0

    for spec in FIELDS:

        if spec["fieldname"] not in missing:
            continue

        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "Issue",
            "insert_after": "ss97_technician",
            **spec
        }).insert()

        created += 1

    frappe.clear_cache(doctype="Issue")

    result = preflight()

    if result["missing"] or result["conflicts"]:
        frappe.throw("Schema cockpit incomplet.")

    for spec in FIELDS:

        if not frappe.db.has_column(
            "Issue", spec["fieldname"]
        ):

            frappe.throw(
                "Colonne absente : " + spec["fieldname"]
            )

    return {
        "created": created,
        "verified": len(FIELDS),
        "missing": 0,
        "conflicts": 0
    }
