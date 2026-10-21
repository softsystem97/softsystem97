"""Chromium tests of real Cyber template, HTTP fixtures only, no live authentication."""

import argparse
import json
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from jinja2 import DictLoader, Environment, select_autoescape
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chromium", default="/usr/bin/chromium")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    template = (root / "softsystem97/www/ss97-cyber.html").read_text()
    bridge = """<script>window.frappe={csrf_token:'synthetic-browser-only',call:async o=>{
      const response=await fetch('/api/method/'+o.method,{method:o.type||'GET',
        headers:{'Content-Type':'application/x-www-form-urlencoded','X-Frappe-CSRF-Token':'synthetic-browser-only'},
        ...(o.type==='POST'?{body:new URLSearchParams(o.args)}:{})});
      if(!response.ok)throw Error('denied');return await response.json();}};</script>"""
    env = Environment(
        loader=DictLoader(
            {
                "page.html": template,
                "templates/web.html": '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>'
                + bridge
                + "{% block page_content %}{% endblock %}</body></html>",
            }
        ),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("page.html").render(cyber_views=["client", "direction"])
    counts = 0

    def passed(label):
        nonlocal counts
        counts += 1
        print("PASS " + label, flush=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=args.chromium, headless=True)
        page = browser.new_page(viewport={"width": 1200, "height": 900})
        page.set_default_timeout(10000)
        state = {"deny": False, "hold": False, "remote_state": "Awaiting consent"}
        pending = []
        requests = []

        def data(value=1):
            return {
                "indicators": {
                    "equipment": value,
                    "companies": value,
                    "maintenance_due": 2,
                    "backups_to_verify": 3,
                    "pending_audits": 4,
                    "high_risks": 5,
                    "urgent_actions": 0,
                    "completed_audits": 1,
                    "open_risks": 1,
                    "critical_incidents": 0,
                    "pending_actions": 1,
                    "open_incidents": 1,
                    "alerts": 0,
                    "active_contracts": 0,
                    "open_vulnerabilities": 0,
                },
                "companies": [{"customer": "Synthetic A"}],
                "tables": {
                    "assets": [
                        {
                            "name": "ASSET-A",
                            "asset_name": "<img src=x onerror=window.SS97_XSS=1>",
                        }
                    ],
                    "reports": [{"name": "RPT /?<x>", "approval": "Approved"}],
                    "assistance": [
                        {
                            "name": "REMOTE-MOCK",
                            "state": state["remote_state"],
                            "modified": "revision-1",
                            "billing_basis": "Contract",
                        }
                    ],
                },
                "scope_truncated": False,
                "table_limit": 50,
            }

        def fulfill(route, value=1):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"message": data(value)}),
            )

        def handle(route):
            request = route.request
            path = urlparse(request.url).path
            if path == "/ss97-cyber":
                return route.fulfill(status=200, content_type="text/html", body=html)
            if not path.startswith("/api/method/"):
                return route.abort()
            requests.append((path, request.method, parse_qs(request.post_data or "")))
            if state["deny"]:
                return route.fulfill(
                    status=403, body="{}", content_type="application/json"
                )
            if path.endswith("workspace.load"):
                if state["hold"]:
                    pending.append(route)
                    return
                return fulfill(route)
            if path.endswith("remote_requests.transition"):
                payload = parse_qs(request.post_data or "")
                state["remote_state"] = payload["state"][0]
                return route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "message": {
                                "name": "REMOTE-MOCK",
                                "state": state["remote_state"],
                                "can_start": False,
                            }
                        }
                    ),
                )
            if path.endswith("reports.generate"):
                return route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"message": {"name": "RPT-DRAFT-MOCK"}}),
                )
            if path.endswith("remote_requests.request"):
                return route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"message": {"name": "REMOTE-DEMO"}}),
                )
            return route.abort()

        page.route("**/*", handle)
        page.goto("https://cyber.example.invalid/ss97-cyber")
        page.wait_for_selector("#cyber-kpis dd")
        assert page.locator("#cyber-kpis dd").first.inner_text() == "1"
        assert (
            page.locator("#cyber-kpis").inner_text().find("Sauvegardes à vérifier") >= 0
        )
        assert "undefined" not in page.locator("#cyber-kpis").inner_text()
        assert (
            page.locator("#cyber-kpis dt", has_text="Sauvegardes à vérifier").evaluate(
                "el => el.nextElementSibling.textContent"
            )
            == "3"
        )
        passed("Workspace renders computed indicators and company tables")
        assert page.evaluate("window.SS97_XSS") is None
        assert page.locator("#cyber-tables img").count() == 0
        assert "<img src=x" in page.locator("#cyber-tables").inner_text()
        passed("Equipment labels are rendered as text, not executable HTML")
        assert page.locator("#cyber-tables a").get_attribute(
            "href"
        ) == "/ss97-cyber-report?name=" + quote("RPT /?<x>", safe="")
        passed("Report reference is URL encoded")
        page.get_by_role("button", name="Consentir à la préparation").click()
        page.get_by_role("button", name="Révoquer", exact=True).wait_for()
        page.get_by_role("button", name="Révoquer", exact=True).click()
        page.wait_for_function(
            "!Array.from(document.querySelectorAll('#cyber-tables button')).some(b=>b.textContent==='Révoquer')"
        )
        transitions = [
            r for r in requests if r[0].endswith("remote_requests.transition")
        ]
        assert [r[2]["state"][0] for r in transitions] == ["Consented", "Revoked"]
        assert all(r[1] == "POST" for r in transitions)
        passed(
            "Client consent and revocation controls send scoped management transitions only"
        )
        page.locator("#cyber-report-generate input[name=customer]").fill("Synthetic A")
        page.locator("#cyber-report-generate input[name=from_date]").fill("2026-10-01")
        page.locator("#cyber-report-generate input[name=to_date]").fill("2026-10-21")
        page.locator("#cyber-report-generate button").click()
        page.wait_for_function(
            "document.querySelector('#cyber-report-result').textContent.includes('RPT-DRAFT-MOCK')"
        )
        report_call = [r for r in requests if r[0].endswith("reports.generate")][-1]
        assert report_call[1] == "POST" and report_call[2]["customer"] == [
            "Synthetic A"
        ]
        passed("Manager report form requests a draft through POST")
        state["hold"] = True
        page.click("#cyber-load")
        page.wait_for_timeout(100)
        page.select_option("#cyber-view", "direction")
        page.wait_for_timeout(100)
        assert len(pending) == 2
        fulfill(pending[1], 99)
        fulfill(pending[0], 1)
        page.wait_for_function(
            "document.querySelector('#cyber-kpis dd')?.textContent==='99'"
        )
        passed("Late workspace response cannot overwrite the newer role view")
        state["hold"] = False
        state["deny"] = True
        page.click("#cyber-load")
        page.wait_for_function(
            "document.querySelector('#cyber-error').textContent.length>0"
        )
        assert page.locator("#cyber-kpis dd").count() == 0
        assert page.locator("#cyber-tables table").count() == 0
        passed("Permission or session error clears previous company data")
        state["deny"] = False
        page.locator("#cyber-assistance input[name=customer]").fill("Synthetic A")
        page.locator("#cyber-assistance input[name=issue]").fill("ISS-DEMO")
        page.locator("#cyber-assistance button").click()
        page.wait_for_function(
            "document.querySelector('#cyber-assistance-result').textContent.includes('REMOTE-DEMO')"
        )
        call = [r for r in requests if r[0].endswith("remote_requests.request")][-1]
        assert call[1] == "POST" and call[2]["issue"] == ["ISS-DEMO"]
        assert (
            "aucun accès distant démarré"
            in page.locator("#cyber-assistance-result").inner_text()
        )
        assert not any("start" in r[0] for r in requests)
        passed("Assistance form records a POST request, never a remote-engine start")
        browser.close()
    print(
        f"TOTAL: {counts} Cyber browser scenarios passed (HTTP fixtures, no live session)."
    )


if __name__ == "__main__":
    main()
