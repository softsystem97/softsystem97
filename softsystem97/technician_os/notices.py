"""Idempotent candidate mail outbox; sending is separately opt-in on each site.

QUEUED means accepted by Frappe Email Queue, never proof of SMTP delivery.
No identity files, contracts, exam answers, RIBs or sensitive data are emailed.
"""

from uuid import uuid4

import frappe
from frappe.utils import now_datetime


NOTICE = "SS97 Technician Notice"
MESSAGES = {
    "APPLIED": ("Candidature bien reçue", "Nous avons bien reçu votre candidature. Votre dossier est en attente d'étude."),
    "IN_REVIEW": ("Invitation à la présélection", "Votre candidature est en étude. Connectez-vous à votre espace SS97 TECH OS pour découvrir l'examen de votre spécialité."),
    "EXAM_VALIDATED": ("Examen de présélection validé", "Votre résultat technique a été vérifié. Le contrôle de vos justificatifs reste nécessaire."),
    "DOCUMENTS_VALIDATED": ("Justificatifs vérifiés", "Vos justificatifs ont été contrôlés par notre équipe. Le contrat freelance reste à valider."),
    "CONTRACT_SIGNED": ("Contrat freelance enregistré", "La vérification externe de votre contrat a été enregistrée. L'habilitation est encore soumise aux contrôles de sécurité."),
    "ACTIVE": ("Espace professionnel autorisé", "Votre habilitation est active. Connectez-vous à votre espace personnel pour consulter vos missions autorisées."),
    "SUSPENDED": ("Habilitation suspendue", "Votre accès professionnel est temporairement suspendu. Contactez Soft System 97."),
    "REJECTED": ("Suite donnée à votre candidature", "Votre candidature n'a pas été retenue à cette étape. Contactez Soft System 97 pour toute question."),
}


def _mail_enabled():
    config = frappe.conf.get("ss97_tech_email_notifications") or {}
    return isinstance(config, dict) and config.get("enabled") is True


def stage_notice(profile, kind, event_key):
    """Record exactly one notice for a committed workflow transition."""
    if kind not in MESSAGES or not isinstance(event_key, str) or len(event_key) != 36:
        raise ValueError("Événement de notification invalide.")
    if frappe.db.exists(NOTICE, {"event_key": event_key}):
        return
    state = "PENDING" if _mail_enabled() else "HELD"
    notice = frappe.get_doc({
        "doctype": NOTICE, "notice_id": str(uuid4()),
        "profile": profile.name, "candidate_user": profile.candidate_user,
        "event_key": event_key, "kind": kind, "state": state,
    }).insert(ignore_permissions=True)
    if state == "PENDING":
        frappe.enqueue(
            "softsystem97.technician_os.notices.deliver_notice",
            queue="short", enqueue_after_commit=True, notice_id=notice.name,
        )


def deliver_notice(notice_id):
    """Private background worker; only stages delivery to native Email Queue."""
    if not _mail_enabled():
        return
    notice = frappe.get_doc(NOTICE, notice_id, for_update=True)
    if notice.state != "PENDING" or notice.kind not in MESSAGES:
        return
    email = frappe.db.get_value("User", notice.candidate_user, "email")
    if not email:
        notice.state = "ERROR"
        notice.save(ignore_permissions=True)
        return
    subject, body = MESSAGES[notice.kind]
    try:
        queued = frappe.sendmail(
            recipients=[email], subject="Soft System 97 — " + subject,
            message=("Bonjour,\n\n" + body + "\n\n"
                     "Votre espace : https://app.softsystem97.com/ss97-tech-os\n\n"
                     "Équipe Soft System 97"),
            delayed=True, reference_doctype=NOTICE, reference_name=notice.name,
            attachments=[],
        )
        if not queued or not getattr(queued, "name", None):
            notice.state = "ERROR"
            notice.save(ignore_permissions=True)
            return
    except Exception:
        notice.state = "ERROR"
        notice.save(ignore_permissions=True)
        return
    notice.state = "QUEUED"
    notice.queued_at = now_datetime()
    notice.save(ignore_permissions=True)
