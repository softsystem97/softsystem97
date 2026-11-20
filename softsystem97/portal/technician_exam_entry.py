"""Session-scoped bridge to the legacy SS97 technician application exam.

This only retrieves an existing candidate's own invitation.  It cannot start
an attempt, mark an exam as passed, approve a candidate or activate a worker.
"""

import re
from urllib.parse import urlencode

import frappe


APPLICATION = "SS97 Technician Application"
EXAM_READY_STATES = frozenset({
    "Examen technique", "Examen envoyé", "Examen à passer",
    "Examen en cours", "Test technique envoyé",
})
LEGACY_NAV_ROLES = frozenset({
    "System Manager", "Administrator", "SS97 Administrator", "SS97 Admin",
    "SS97 Technician", "SS97 Support", "Customer", "SS97 Client",
})


def _logged_in_user():
    user = frappe.session.user
    if not user or user == "Guest" or not frappe.db.get_value("User", user, "enabled"):
        frappe.throw("Connexion au compte candidat requise.", frappe.PermissionError)
    return user


@frappe.whitelist(methods=["GET"])
def get_my_portal_roles():
    """Compatibility with legacy website navigation; never accepts a user ID."""
    user = _logged_in_user()
    return sorted(LEGACY_NAV_ROLES.intersection(frappe.get_roles(user)))


@frappe.whitelist(methods=["GET"])
def get_my_exam_entry():
    """Return only the current user's already-issued exam URL.

    The legacy recruitment DocType differs from the newer TECH OS pilot's
    `SS97 Technician Profile`.  Its examination invitation must remain bound
    to the registered `portal_user`, not to a claimed query-string e-mail.
    """
    user = _logged_in_user()
    if not frappe.db.table_exists(APPLICATION):
        frappe.throw("Dossiers techniciens indisponibles.", frappe.PermissionError)

    applications = frappe.get_all(
        APPLICATION,
        filters={"portal_user": user},
        fields=["name", "email_id", "recruitment_status", "exam_access_token"],
        limit_page_length=2,
    )
    if len(applications) != 1:
        frappe.throw("Aucun dossier d'examen unique lié à ce compte.", frappe.PermissionError)

    application = applications[0]
    if (not isinstance(application.get("email_id"), str)
            or application["email_id"].casefold() != user.casefold()
            or application.get("recruitment_status") not in EXAM_READY_STATES):
        frappe.throw("L'examen de ce dossier n'est pas disponible.", frappe.PermissionError)

    application_id = application.get("name")
    token = application.get("exam_access_token")
    if (not isinstance(application_id, str)
            or not re.fullmatch(r"SS97-TECH-\d{1,12}", application_id)
            or not isinstance(token, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{12,128}", token)):
        frappe.throw("Invitation d'examen incomplète.", frappe.PermissionError)

    return {"application": application_id,
            "url": "/examen-technicien?" + urlencode({"app": application_id, "token": token})}
