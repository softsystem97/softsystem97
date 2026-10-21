"""Explicit manager-triggered sync. No scheduler, cursor advance or external side effect."""

import hashlib
from datetime import datetime, timezone

import frappe

from . import permissions as access
from .connectors.wazuh import ConnectorError, fetch_alerts
from .operations_model import generated


def _synchronize(configuration, since, transport=None):
    if not access.manager():
        frappe.throw("Cyber management required", frappe.PermissionError)
    config = frappe.get_doc("SS97 Cyber Wazuh Config", configuration)
    config.check_permission("read")
    access.require_customer(config.customer, write=True)
    if not config.enabled:
        frappe.throw("Wazuh configuration disabled", frappe.PermissionError)
    # Lock configuration so simultaneous pulls cannot create duplicate incidents.
    locked = frappe.db.sql(
        "select name, enabled, modified from `tabSS97 Cyber Wazuh Config` where name=%s for update",
        (config.name,),
        as_dict=True,
    )
    if (
        not locked
        or not locked[0].enabled
        or str(locked[0].modified) != str(config.modified)
    ):
        frappe.throw("Configuration changed; retry the request", frappe.PermissionError)
    company = frappe.db.sql(
        "select authorization_status, authorization_reference from `tabSS97 Cyber Company` where customer=%s for update",
        (config.customer,),
        as_dict=True,
    )
    if (
        not company
        or company[0].authorization_status != "Granted"
        or not company[0].authorization_reference
    ):
        frappe.throw("Company authorization revoked", frappe.PermissionError)
    counts = {"received": 0, "accepted": 0, "duplicates": 0, "ignored": 0}
    error = None
    truncated = False
    frappe.db.savepoint("cyber_wazuh_batch")
    try:
        alerts, truncated = fetch_alerts(
            config.api_url,
            config.username,
            config.get_password("password"),
            since,
            frappe.conf.get("ss97_wazuh_allowed_hosts") or [],
            transport=transport,
        )
        counts["received"] = len(alerts)
        mappings = {row.agent_id: row.asset for row in config.mappings}
        for alert in alerts:
            asset = mappings.get(alert.agent_id)
            if (
                not asset
                or frappe.db.get_value("SS97 Cyber Asset", asset, "customer")
                != config.customer
            ):
                counts["ignored"] += 1
                continue
            key = hashlib.sha256(
                (
                    config.customer
                    + "\0"
                    + config.api_url.rstrip("/")
                    + "\0"
                    + alert.event_id
                ).encode()
            ).hexdigest()
            if frappe.db.sql(
                "select name from `tabSS97 Cyber Sync Event` where event_key=%s for update",
                (key,),
            ):
                counts["duplicates"] += 1
                continue
            severity = (
                "Critical"
                if alert.level >= 15
                else "High"
                if alert.level >= 12
                else "Medium"
                if alert.level >= 7
                else "Low"
            )
            incident = None
            if config.create_incidents and alert.level >= config.minimum_level:
                incident = (
                    frappe.get_doc(
                        {
                            "doctype": "SS97 Cyber Incident",
                            "customer": config.customer,
                            "title": "Wazuh alert requiring review",
                            "asset": asset,
                            "severity": severity,
                            "description": "Verified indexer alert reference retained; raw payload not stored.",
                        }
                    )
                    .insert()
                    .name
                )
            with generated():
                frappe.get_doc(
                    {
                        "doctype": "SS97 Cyber Sync Event",
                        "customer": config.customer,
                        "configuration": config.name,
                        "provider": "Wazuh indexer",
                        "event_key": key,
                        "asset": asset,
                        "severity": severity,
                        "occurred_at": datetime.fromisoformat(
                            alert.occurred_at.replace("Z", "+00:00")
                        )
                        .astimezone(timezone.utc)
                        .replace(tzinfo=None),
                        "incident": incident,
                    }
                ).insert(ignore_permissions=True)
            counts["accepted"] += 1
    except (
        frappe.QueryDeadlockError,
        frappe.QueryTimeoutError,
        frappe.DuplicateEntryError,
        frappe.UniqueValidationError,
    ):
        raise  # Native deadlock handling may already have removed the savepoint.
    except Exception as exc:  # noqa: BLE001 -- redact all upstream/DB errors at this boundary
        frappe.db.rollback(save_point="cyber_wazuh_batch")
        error = (
            exc.args[0]
            if isinstance(exc, ConnectorError)
            and exc.args
            and isinstance(exc.args[0], str)
            else "sync_failed"
        )
        # No exception text, traceback, credentials, URL or payload in audit records.
        if error not in {
            "invalid_origin",
            "invalid_since",
            "invalid_alert",
            "http_error",
            "response_too_large",
            "invalid_response",
            "transport_or_response_error",
        }:
            error = "sync_failed"
        counts["accepted"] = counts["duplicates"] = counts["ignored"] = 0
    with generated():
        run = frappe.get_doc(
            dict(
                doctype="SS97 Cyber Sync Run",
                customer=config.customer,
                configuration=config.name,
                status="Error" if error else "Success",
                error_code=error,
                truncated=int(truncated),
                **counts,
            )
        ).insert(ignore_permissions=True)
    return dict(run=run.name, status=run.status, truncated=truncated, **counts)


class SyncRetryConflict(frappe.ValidationError):
    http_status_code = 409


def synchronize(configuration, since, transport=None):
    try:
        return _synchronize(configuration, since, transport)
    except (
        frappe.QueryDeadlockError,
        frappe.QueryTimeoutError,
        frappe.DuplicateEntryError,
        frappe.UniqueValidationError,
    ):
        frappe.throw(
            "Concurrent synchronization conflict; rollback and retry", SyncRetryConflict
        )


@frappe.whitelist(methods=["POST"])
def sync(configuration, since):
    access.require_write_session()
    # Transport injection is available to server-side tests only, never HTTP.
    return synchronize(configuration, since)
