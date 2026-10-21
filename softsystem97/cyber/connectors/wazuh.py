"""Wazuh INDEXER OpenSearch alerts adapter, not the manager /agents API.

Never logs payloads, credentials, response text or URLs. Transport injected in
unit tests. HTTPS origin is explicitly allowlisted by the bench administrator.
"""

import ipaddress
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

import requests


class ConnectorError(Exception):
    pass


@dataclass(frozen=True)
class Alert:
    event_id: str
    agent_id: str
    occurred_at: str
    level: int


def checked_origin(url, allowed_hosts):
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
            or parsed.port not in (None, 443, 9200)
            or parsed.hostname not in set(allowed_hosts)
        ):
            raise ValueError()
        # Even an allowlist must not target link-local metadata or loopback.
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            address = None
        if address and (
            address.is_loopback or address.is_link_local or address.is_unspecified
        ):
            raise ValueError()
        return url.rstrip("/")
    except (ValueError, TypeError):
        raise ConnectorError("invalid_origin") from None


def parse_alert(hit):
    try:
        source = hit["_source"]
        event_id, agent = hit["_id"], source["agent"]["id"]
        level = source["rule"]["level"]
        timestamp = source["timestamp"]
        if (
            not isinstance(event_id, str)
            or not 1 <= len(event_id) <= 256
            or not isinstance(agent, str)
            or not 1 <= len(agent) <= 128
            or type(level) is not int
            or not 0 <= level <= 16
            or not isinstance(timestamp, str)
            or len(timestamp) > 64
        ):
            raise ValueError()
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError()
        return Alert(event_id, agent, timestamp, level)
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ConnectorError("invalid_alert") from None


def fetch_alerts(url, username, password, since, allowed_hosts, transport=None):
    origin = checked_origin(url, allowed_hosts)
    try:
        stamp = datetime.fromisoformat(since.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ConnectorError("invalid_since") from None
    post = transport or requests.post
    try:
        response = post(
            origin + "/wazuh-alerts-4.x-*/_search",
            auth=(username, password),
            verify=True,
            allow_redirects=False,
            timeout=(3, 10),
            stream=True,
            json={
                "size": 100,
                "sort": [{"timestamp": "asc"}],
                "_source": ["agent.id", "rule.level", "timestamp"],
                "query": {"range": {"timestamp": {"gte": since}}},
            },
        )
        try:
            if response.status_code != 200:
                raise ConnectorError("http_error")
            raw = bytearray()
            for chunk in response.iter_content(chunk_size=8192):
                raw.extend(chunk)
                if len(raw) > 2_000_000:
                    raise ConnectorError("response_too_large")
            import json

            payload = json.loads(raw)
            hits = payload["hits"]["hits"]
            if not isinstance(hits, list) or len(hits) > 100:
                raise ConnectorError("invalid_response")
            # No automatic paging: a full batch is explicitly marked truncated.
            return [parse_alert(hit) for hit in hits], len(hits) == 100
        finally:
            response.close()
    except ConnectorError:
        raise
    except Exception:  # noqa: BLE001 -- upstream exceptions must not disclose credentials
        raise ConnectorError("transport_or_response_error") from None
