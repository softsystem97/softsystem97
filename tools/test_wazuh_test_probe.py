"""Offline tests: actual connector normalization with a fictional HTTP transport."""

import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from probe_wazuh_test import ConnectorError, probe


class TestWazuhProbe(unittest.TestCase):
    def setUp(self):
        self.environment = {
            "SS97_WAZUH_TEST_USER": "fictional-user",
            "SS97_WAZUH_TEST_PASSWORD": "fictional-password",
        }
        self.transport = Mock()
        response = Mock(status_code=200)
        hit = {
            "_id": "fake-event",
            "_source": {
                "agent": {"id": "001"},
                "rule": {"level": 15},
                "timestamp": "2026-10-21T00:00:00Z",
            },
        }
        response.iter_content.return_value = [
            json.dumps({"hits": {"hits": [hit, hit]}}).encode()
        ]
        self.transport.return_value = response

    def run_probe(self, **changes):
        args = {
            "url": "https://indexer.example.invalid:9200",
            "host": "indexer.example.invalid",
            "since": "2026-10-21T00:00:00Z",
            "authorized": True,
            "environ": self.environment,
            "transport": self.transport,
        }
        args.update(changes)
        return probe(**args)

    def test_lab_template_stays_disabled_and_secret_free(self):
        template = Path(__file__).resolve().parents[1] / "lab/wazuh/test-config.json"
        config = json.loads(template.read_text())
        for flag in ("enabled", "create_incidents", "remote_administration"):
            self.assertIs(config[flag], False)
        self.assertNotIn("password", config)
        self.assertTrue(config["url"].endswith(".invalid:9200"))

    def test_authorization_required_before_network(self):
        with self.assertRaisesRegex(ConnectorError, "authorization_required"):
            self.run_probe(authorized=False)
        self.transport.assert_not_called()

    def test_credentials_required_before_network(self):
        with self.assertRaisesRegex(ConnectorError, "credentials_required"):
            self.run_probe(environ={})
        self.transport.assert_not_called()

    def test_tls_and_counts_without_identifiers_or_credentials(self):
        result = self.run_probe()
        self.assertEqual(result["alerts_received"], 2)
        self.assertEqual(result["critical_alerts"], 2)
        self.assertEqual(result["duplicate_event_ids"], 1)
        self.assertFalse(result["frappe_written"])
        self.assertEqual(result["incidents_created"], 0)
        self.assertTrue(self.transport.call_args.kwargs["verify"])
        self.assertFalse(self.transport.call_args.kwargs["allow_redirects"])
        for secret in (*self.environment.values(), "fake-event", "001"):
            self.assertNotIn(secret, json.dumps(result))

    def test_host_mismatch_denied_before_network(self):
        with self.assertRaisesRegex(ConnectorError, "invalid_origin"):
            self.run_probe(host="different.example.invalid")
        self.transport.assert_not_called()

    def test_upstream_exception_is_redacted(self):
        self.transport.side_effect = RuntimeError("fictional-password private payload")
        with self.assertRaises(ConnectorError) as error:
            self.run_probe()
        self.assertNotIn("fictional-password", str(error.exception))
        self.assertNotIn("private payload", str(error.exception))


if __name__ == "__main__":
    unittest.main()
