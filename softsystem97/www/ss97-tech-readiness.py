"""Restricted, read-only go-live diagnostics; available while TECH OS is disabled."""

from softsystem97.technician_os.api import _manager


def get_context(context):
    _manager()  # Do not require the TECH OS feature flag for readiness checks.
    context.no_cache = 1
    context.title = "SS97 TECH OS — Préparation à l'ouverture"
