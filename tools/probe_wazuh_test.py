"""Explicit read-only Wazuh TEST indexer probe; no Frappe/database or incident writes.

Credentials: SS97_WAZUH_TEST_USER and SS97_WAZUH_TEST_PASSWORD in the private
process environment. Never pass credentials on the command line. HTTPS/TLS and
origin validation reuse the production connector. No network call on import.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from softsystem97.cyber.connectors.wazuh import ConnectorError, fetch_alerts


def probe(url, host, since, *, authorized=False, environ=None, transport=None):
    if not authorized:
        raise ConnectorError("test_read_authorization_required")
    environ = os.environ if environ is None else environ
    username = environ.get("SS97_WAZUH_TEST_USER")
    password = environ.get("SS97_WAZUH_TEST_PASSWORD")
    if not username or not password:
        raise ConnectorError("test_credentials_required")
    alerts, truncated = fetch_alerts(
        url, username, password, since, [host], transport=transport
    )
    return {
        "mode": "read_only_test_probe",
        "alerts_received": len(alerts),
        "critical_alerts": sum(alert.level >= 15 for alert in alerts),
        "duplicate_event_ids": len(alerts) - len({alert.event_id for alert in alerts}),
        "truncated": truncated,
        "frappe_written": False,
        "incidents_created": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument(
        "--host", required=True, help="Explicit authorized TEST hostname"
    )
    parser.add_argument("--since", required=True, help="ISO timestamp with timezone")
    parser.add_argument("--authorize-test-read", action="store_true")
    args = parser.parse_args()
    try:
        result = probe(
            args.url, args.host, args.since, authorized=args.authorize_test_read
        )
    except ConnectorError as error:
        print(json.dumps({"ok": False, "code": str(error)}))
        return 1
    print(json.dumps({"ok": True, **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
