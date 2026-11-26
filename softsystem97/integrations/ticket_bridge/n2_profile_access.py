"""Qualification commerciale N2."""

from softsystem97.technician_os.rules import exact_track_role

N2_ROLE = "SS97 Technicien N2"


def qualified(profile, roles):
    return bool(
        profile
        and profile.get("track") == "L2"
        and profile.get("state") == "ACTIVE"
        and profile.get("engagement") == "FREELANCE"
        and exact_track_role(roles, "L2")
    )


def enforce(user, roles):
    import frappe

    if not frappe.db.table_exists(
        "SS97 Technician Profile"
    ):
        frappe.throw(
            "Profil N2 indisponible.",
            frappe.PermissionError
        )

    profiles = frappe.get_all(
        "SS97 Technician Profile",
        filters={"candidate_user": user},
        fields=["track", "state", "engagement"],
        limit_page_length=2
    )

    if len(profiles) != 1 or not qualified(
        profiles[0], roles
    ):
        frappe.throw(
            "Habilitation N2 inactive ou invalide.",
            frappe.PermissionError
        )
