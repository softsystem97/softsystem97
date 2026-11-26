"""Conditions explicites du cockpit commercial N2."""

PRODUCTION_SITE = "erpnext-xyq-hym.v.frappe.cloud"

N2_ROLE = "SS97 Technicien N2"

AUTHORIZER = (
    "softsystem97.integrations.ticket_bridge."
    "live_authorizer.authorize_ticket_operation"
)


def commercial_allowed(site, conf, config):

    if site != PRODUCTION_SITE:
        return False

    if not isinstance(config, dict):
        return False

    if any(conf.get(key) for key in (
        "allow_tests",
        "ss97_stripe_test_site",
        "ignore_csrf",
    )):
        return False

    remote = conf.get("ss97_remote_assist") or {}

    if not isinstance(remote, dict):
        return False

    if remote.get("enabled"):
        return False

    return (
        config.get("enabled") is True
        and config.get("compatibility_confirmed") is True
        and config.get("cockpit_commercial_enabled") is True
        and config.get("profile_required") is True
        and config.get("historical_integration") is True
        and config.get("enforce_paid_interventions") is True
        and config.get("issue_scripts_reviewed") is True
        and config.get("technician_role") == N2_ROLE
        and config.get("business_authorizer") == AUTHORIZER
        and bool(config.get("writer_user"))
        and config.get("writer_user") not in (
            "Administrator", "Guest"
        )
    )


def managed_ticket(site, config, previous, doc):

    if site == "audit.n2.localhost":
        return True

    if site != PRODUCTION_SITE:
        return False

    config = config if isinstance(config, dict) else {}

    return (
        config.get("technician_role") == N2_ROLE
        or any(
            record and (
                record.get("ss97_timer_resumed_on")
                or record.get("ss97_timer_status")
                in ("running", "paused")
            )
            for record in (previous, doc)
        )
    )
