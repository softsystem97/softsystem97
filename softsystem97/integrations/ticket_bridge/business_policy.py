"""Confirmed historical catalogue constraints, NOT a business authorizer.

No authorize_ticket_operation is provided: payment proof, actor-specific action
rights and deployed Workflow/Server Scripts are not in the received sources.
Never register catalogue predicates as business_authorizer. No activation occurs.
"""


def native_status(ticket_status):
    """Reject unknown/unmapped states rather than silently reopening as Open."""
    from integrations.ss97_tickets.specs import STATUS_TO_NATIVE

    if not isinstance(ticket_status, str) or ticket_status not in STATUS_TO_NATIVE:
        raise ValueError("Statut historique absent du mapping confirmé.")
    return STATUS_TO_NATIVE[ticket_status]


def is_declared_transition(source, target):
    """Catalogue edge only; says nothing about role, payment, consent or ownership.

    Keep exact runtime states: merging aliases could broaden the original graph.
    """
    from integrations.ss97_tickets.specs import STATUS_ACTIONS

    return any(
        destination == target for _, destination in STATUS_ACTIONS.get(source, [])
    )


def catalogue_gaps():
    """Expose source contradictions for review, never resolve them by guessing."""
    from integrations.ss97_tickets.specs import (
        STATUS_ALIAS_TO_OFFICIAL,
        STATUS_TO_NATIVE,
        TICKET_STATUSES,
    )

    return {
        "unmapped_statuses": [s for s in TICKET_STATUSES if s not in STATUS_TO_NATIVE],
        "alias_native_conflicts": [
            alias
            for alias, canonical in STATUS_ALIAS_TO_OFFICIAL.items()
            if alias in STATUS_TO_NATIVE
            and canonical in STATUS_TO_NATIVE
            and STATUS_TO_NATIVE[alias] != STATUS_TO_NATIVE[canonical]
        ],
        "authorization_provider_available": False,
    }
