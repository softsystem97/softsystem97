"""Native WSGI Cyber checks on a disposable site, using synthetic accounts only."""

import argparse
import json
import os
import re
import secrets
from pathlib import Path

import frappe
from werkzeug.test import Client
from werkzeug.wrappers import Response

from softsystem97.cyber.permissions import DOCTYPES
from softsystem97.tests.test_cyber import TestCyber


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True)
    args = parser.parse_args()
    if not args.site.startswith(("audit.", "test_")):
        parser.error("Disposable audit/test site required")
    sites = str(Path.cwd() / "sites")
    os.chdir(sites)
    from frappe import app as frappe_app

    def connect():
        frappe.init(site=args.site, sites_path=sites)
        frappe.connect()
        frappe.set_user("Administrator")

    connect()
    if not frappe.conf.allow_tests or frappe.conf.get("ignore_csrf"):
        raise RuntimeError("allow_tests and native CSRF protection required")
    old_site, old_sites = frappe_app._site, frappe_app._sites_path
    fixture = False
    scope = []
    count = 0

    def passed(label):
        nonlocal count
        count += 1
        print("PASS " + label, flush=True)

    try:
        TestCyber.setUpClass()
        fixture = True
        test = TestCyber()
        test.setUp()
        scope = TestCyber.customers
        own_asset = test.asset()
        own_asset.asset_name = "<script>window.SS97_REPORT_XSS=1</script>"
        own_asset.save()
        from softsystem97.cyber import reports

        approved = reports.generate(test.a, frappe.utils.today(), frappe.utils.today())
        doc = frappe.get_doc("SS97 Cyber Report", approved["name"])
        reports.approve(doc.name, str(doc.modified))
        draft = reports.generate(test.a, frappe.utils.today(), frappe.utils.today())
        foreign_report = reports.generate(
            test.b, frappe.utils.today(), frappe.utils.today()
        )
        doc = frappe.get_doc("SS97 Cyber Report", foreign_report["name"])
        reports.approve(doc.name, str(doc.modified))
        frappe.set_user("Administrator")
        issue = frappe.get_doc(
            {
                "doctype": "Issue",
                "subject": "Synthetic Cyber HTTP assistance",
                "customer": test.a,
            }
        ).insert()
        issue_name = issue.name
        foreign = test.asset(test.b)
        from frappe.utils.password import update_password

        password = secrets.token_urlsafe(32)
        for user in (TestCyber.client, TestCyber.tech):
            update_password(user, password)
        frappe.db.commit()
        frappe.destroy()
        frappe_app._site, frappe_app._sites_path = args.site, sites
        client = Client(frappe_app.application, Response)
        base = "https://" + args.site
        prefix = "/api/method/softsystem97.cyber.api."

        def call(method, path, **kw):
            response = client.open(
                path, method=method, base_url=base, buffered=True, **kw
            )
            response.close()
            return response

        assert (
            call(
                "GET", prefix + "dashboard", query_string={"customer": test.a}
            ).status_code
            == 403
        )
        assert call("GET", "/ss97-cyber").status_code == 403
        passed("Anonymous dashboard and page denied")
        assert (
            call(
                "POST",
                "/api/method/login",
                data={"usr": TestCyber.client, "pwd": password},
            ).status_code
            == 200
        )
        page = call("GET", "/ss97-cyber")
        assert page.status_code == 200, page.status_code
        body = page.get_data(as_text=True)
        token = re.search(r"frappe\.csrf_token\s*=\s*[\"\x27]([^\"\x27]+)", body)
        assert (
            token
            and token.group(1) not in ("None", "undefined", "")
            and "cyber-kpis" in body
        )
        assert "no-store" in page.headers.get("Cache-Control", "")
        headers = {"X-Frappe-CSRF-Token": token.group(1)}
        passed("Native client login renders protected uncached dashboard")
        response = call("GET", prefix + "dashboard", query_string={"customer": test.a})
        assert (
            response.status_code == 200 and response.json["message"]["equipment"] == 1
        )
        assert (
            call(
                "GET", prefix + "dashboard", query_string={"customer": test.b}
            ).status_code
            == 403
        )
        passed("Client KPIs scoped; other company denied")
        data = call(
            "GET",
            "/api/method/softsystem97.cyber.workspace.load",
            query_string={"view": "client"},
        )
        assert data.status_code == 200
        assert {row["customer"] for row in data.json["message"]["companies"]} == {
            test.a
        }
        assert (
            call(
                "GET",
                "/api/method/softsystem97.cyber.workspace.load",
                query_string={"view": "direction"},
            ).status_code
            == 403
        )
        passed("Role workspace refuses direction access to client")
        printable = call(
            "GET", "/ss97-cyber-report", query_string={"name": approved["name"]}
        )
        assert printable.status_code == 200, printable.status_code
        html = printable.get_data(as_text=True)
        assert "<script>window.SS97_REPORT_XSS=1</script>" not in html
        # Frappe may already strip the dangerous Data field on save.
        assert "equipment" in html and "<table>" in html
        if "window.SS97_REPORT_XSS" in html:
            assert "&lt;script&gt;" in html
        (Path(sites).parent / "logs/cyber-report-preview.html").write_text(html)
        assert (
            call(
                "GET", "/ss97-cyber-report", query_string={"name": draft["name"]}
            ).status_code
            == 403
        )
        assert (
            call(
                "GET",
                "/ss97-cyber-report",
                query_string={"name": foreign_report["name"]},
            ).status_code
            == 403
        )
        passed("Printable report is escaped; drafts and other company denied")
        remote = call(
            "POST",
            "/api/method/softsystem97.cyber.remote_requests.request",
            headers=headers,
            data={"customer": test.a, "issue": issue_name},
        )
        assert remote.status_code == 200, remote.status_code
        assert remote.json["message"]["remote_engine_connected"] is False
        passed("Client records an assistance request without starting an engine")
        denied_sync = call(
            "POST",
            "/api/method/softsystem97.cyber.wazuh_sync.sync",
            headers=headers,
            data={"configuration": "unavailable", "since": "2026-10-20T00:00:00Z"},
        )
        assert denied_sync.status_code == 403
        passed("Client cannot trigger indexer access")
        response = call(
            "GET",
            "/api/resource/SS97 Cyber Asset",
            query_string={"fields": json.dumps(["name", "customer"])},
        )
        assert response.status_code == 200 and all(
            row["customer"] == test.a for row in response.json["data"]
        )
        assert (
            call("GET", "/api/resource/SS97 Cyber Asset/" + foreign.name).status_code
            == 403
        )
        passed("Native REST list and document enforce company isolation")
        response = call(
            "POST",
            prefix + "create_record",
            headers=headers,
            data={
                "kind": "asset",
                "values": json.dumps(
                    {
                        "customer": test.a,
                        "asset_name": "Denied client write",
                        "asset_type": "Computer",
                    }
                ),
            },
        )
        assert response.status_code == 403
        passed("Client cannot create asset over HTTP")
        assert call("POST", "/api/method/logout", headers=headers).status_code == 200
        assert call(
            "GET", prefix + "dashboard", query_string={"customer": test.a}
        ).status_code in (401, 403)
        passed("Logout revokes dashboard access")
        assert (
            call(
                "POST",
                "/api/method/login",
                data={"usr": TestCyber.tech, "pwd": password},
            ).status_code
            == 200
        )
        fresh = call(
            "POST",
            prefix + "create_record",
            data={
                "kind": "asset",
                "values": json.dumps(
                    {
                        "customer": test.a,
                        "asset_name": "Denied fresh session",
                        "asset_type": "Server",
                    }
                ),
            },
        )
        assert fresh.status_code == 403
        passed("Fresh session cannot write Cyber data before obtaining CSRF")
        page = call("GET", "/ss97-cyber")
        body = page.get_data(as_text=True)
        token = re.search(r"frappe\.csrf_token\s*=\s*[\"\x27]([^\"\x27]+)", body)
        headers = {"X-Frappe-CSRF-Token": token.group(1)}
        payload = {
            "kind": "asset",
            "values": json.dumps(
                {
                    "customer": test.a,
                    "asset_name": "HTTP fake server",
                    "asset_type": "Server",
                }
            ),
        }
        response = call("POST", prefix + "create_record", data=payload)
        assert response.status_code in (400, 403), ("csrf status", response.status_code)
        assert (
            call("GET", prefix + "create_record", query_string=payload).status_code
            == 403
        )
        passed("Native CSRF and POST requirements enforced")
        assert (
            call(
                "POST", prefix + "create_record", headers=headers, data=payload
            ).status_code
            == 200
        )
        payload["values"] = json.dumps(
            {
                "customer": test.b,
                "asset_name": "Denied other company",
                "asset_type": "Server",
            }
        )
        assert (
            call(
                "POST", prefix + "create_record", headers=headers, data=payload
            ).status_code
            == 403
        )
        passed("Authorized technician creates only in assigned company")
        print(
            f"TOTAL: {count} native Cyber HTTP scenarios passed; no external system accessed."
        )
    finally:
        frappe.destroy()
        frappe_app._site, frappe_app._sites_path = old_site, old_sites
        if fixture:
            connect()
            # Test-only cleanup of fixture scopes. Production deletion remains denied.
            for dt in DOCTYPES:
                names = (
                    frappe.get_all(
                        dt, filters={"customer": ["in", scope]}, pluck="name"
                    )
                    if scope
                    else []
                )
                for name in names:
                    if dt == "SS97 Cyber Company":
                        frappe.db.delete("SS97 Cyber Member", {"parent": name})
                    if dt == "SS97 Cyber Audit":
                        frappe.db.delete("SS97 Cyber Check", {"parent": name})
                if scope:
                    frappe.db.delete(dt, {"customer": ["in", scope]})
            for issue_name in (
                frappe.get_all(
                    "Issue", filters={"customer": ["in", scope]}, pluck="name"
                )
                if scope
                else []
            ):
                frappe.delete_doc("Issue", issue_name)
            frappe.db.commit()
            TestCyber.tearDownClass()
            frappe.destroy()


if __name__ == "__main__":
    main()
