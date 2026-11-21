"""N4 ticket bridge qualification requirements, evaluated without database access."""

N4_ROLE = "SS97 Technicien N4"


def profile_flag_valid(role, required):
    if role == N4_ROLE:
        return required is True
    return required is False


def qualified_n4(profile, roles):
    from softsystem97.technician_os.rules import exact_track_role
    return bool(
        profile and profile.get("state") == "ACTIVE"
        and profile.get("track") == "CYBER"
        and profile.get("engagement") == "FREELANCE"
        and exact_track_role(roles, "CYBER")
    )
