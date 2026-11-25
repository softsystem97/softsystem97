"""Validation navigateur N2 sur site de test uniquement."""

import sys
import json


def browser_test():

    from playwright.sync_api import (
        sync_playwright, expect
    )

    data = json.load(sys.stdin)

    base = data["base"]
    ticket = data["ticket"]

    assert base.startswith("http://127.0.0.1:")

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        try:

            def login(account):

                context = browser.new_context(
                    viewport={
                        "width":1280,
                        "height":900
                    }
                )

                response = context.request.post(
                    base + "/api/method/login",
                    form={
                        "usr":account["email"],
                        "pwd":account["password"]
                    }
                )

                assert response.status == 200

                response = context.request.get(
                    base +
                    "/api/method/frappe.auth.get_logged_user"
                )

                assert (
                    response.json()["message"]
                    == account["email"]
                )

                return context

            tech = login(data["tech"])

            # SS97 COMMERCIAL ACCESS TEST

            availability = (
                base +
                "/api/method/softsystem97.integrations."
                "ticket_bridge.cockpit_api.availability"
            )

            anonymous = browser.new_context()

            denied = anonymous.request.get(
                availability
            )

            assert denied.status in (401, 403)

            anonymous.close()

            allowed = tech.request.get(
                availability
            )

            assert allowed.status == 200

            assert allowed.json()["message"] == {
                "enabled": True,
                "route": "/espace-technicien/cockpit-n2"
            }

            print("ACCES ANONYME BLOQUE : OK")
            print("ACCES COCKPIT COMMERCIAL : OK")


            page = tech.new_page()

            page.set_default_timeout(30000)

            page.goto(
                base + "/espace-technicien/cockpit-n2"
            )

            expect(
                page.locator("#tickets option").first
            ).to_be_attached()

            expect(
                page.locator("#tickets")
            ).to_be_enabled()

            page.locator("#tickets").select_option(
                ticket
            )

            expect(
                page.locator("#start")
            ).to_be_enabled()

            print("CONNEXION TECHNICIEN : OK")

            page.locator("#start").click()

            expect(
                page.locator("#hold")
            ).to_be_enabled()

            print("DEMARRAGE GRAPHIQUE : OK")

            expect(
                page.locator("#work")
            ).not_to_have_text(
                "00:00:00",
                timeout=10000
            )

            print("CHRONOMETRE DYNAMIQUE : OK")

            page.locator("#hold").click()

            expect(
                page.locator("#resume")
            ).to_be_enabled()

            expect(
                page.locator("#pause")
            ).not_to_have_text(
                "00:00:00",
                timeout=10000
            )

            print("PAUSE GRAPHIQUE : OK")

            page.locator("#resume").click()

            expect(
                page.locator("#hold")
            ).to_be_enabled()

            print("REPRISE GRAPHIQUE : OK")

            page.locator("#complete").click()

            expect(
                page.locator("#message")
            ).to_contain_text("obligatoires")

            print("RAPPORT VIDE REFUSE : OK")

            page.locator("#diagnostic").fill(
                "Diagnostic informatique complet"
            )

            page.locator("#report").fill(
                "Intervention terminee et materiel controle"
            )

            page.locator("#checklist").check()

            page.locator("#complete").click()

            expect(
                page.locator("#submit-close")
            ).to_be_enabled()

            print("RAPPORT TECHNIQUE : OK")

            page.locator("#submit-close").click()

            expect(
                page.locator("#message")
            ).to_have_text(
                "Rapport transmis a l'administration."
            )

            remaining = page.locator(
                "#tickets option"
            ).evaluate_all(
                "(items) => items.map(x => x.value)"
            )

            assert ticket not in remaining

            print("TRANSMISSION ADMINISTRATIVE : OK")
            print("RETRAIT DU TICKET TECHNICIEN : OK")

            admin = login(data["admin"])

            page = admin.new_page()

            page.goto(
                base + "/administration-n2/interventions"
            )

            expect(
                page.locator("#tickets option").first
            ).to_be_attached()

            expect(
                page.locator("#tickets")
            ).to_be_enabled()

            page.locator("#tickets").select_option(
                ticket
            )

            expect(
                page.locator("#report")
            ).to_contain_text(
                "Intervention terminee"
            )

            print("LECTURE DU RAPPORT : OK")

            expect(
                page.locator("#close")
            ).to_be_disabled()

            page.locator("#approved").check()

            expect(
                page.locator("#close")
            ).to_be_enabled()

            page.locator("#close").click()

            expect(
                page.locator("#message")
            ).to_have_text(
                "Intervention cloturee avec succes."
            )

            print("VALIDATION ADMINISTRATIVE : OK")
            print("CLOTURE GRAPHIQUE : OK")

            tech.close()
            admin.close()

        finally:

            browser.close()

    print("TEST NAVIGATEUR N2 : OK")


def integration_test(browser_python):

    import secrets
    import threading
    import subprocess
    import frappe
    import frappe.app

    from pathlib import Path
    from werkzeug.serving import make_server
    from frappe.utils.password import update_password

    SITE = "audit.n2.localhost"

    frappe.init(
        site=SITE,
        sites_path=str(Path.cwd())
    )

    frappe.connect()

    old_config = frappe.conf.get(
        "ss97_ticket_bridge"
    )

    original = frappe.app.init_request

    server = None
    thread = None
    admin = None

    try:

        assert frappe.local.site == SITE
        assert frappe.conf.db_host == "127.0.0.1"

        assert frappe.conf.db_name.startswith(
            "ss97n2"
        )

        assert frappe.conf.allow_tests is True
        assert frappe.conf.mute_emails is True
        assert frappe.conf.ss97_stripe_test_site is True

        assert (
            frappe.conf.PAYMENTS_LIVE_ENABLED == 0
        )

        assert not frappe.conf.get("ignore_csrf")

        from softsystem97.integrations.stripe.payment_sync import (
            stripe_mode,
            payments_live_enabled
        )

        assert stripe_mode() == "test"
        assert not payments_live_enabled()

        print("ENVIRONNEMENT ISOLE : OK")

        from softsystem97.tests.test_stripe_accounting import (
            TestStripeAccounting
        )

        from softsystem97.integrations.ticket_bridge import (
            api, policy, payment_gate
        )

        frappe.set_user("Administrator")

        frappe.flags.in_test = True
        frappe.in_test = True

        accounts = json.loads(
            (Path.home() /
             "ss97-n2-comptes-lab.json").read_text()
        )

        tech = accounts["technicien"]
        writer = accounts["service"]["email"]

        assert tech["email"].endswith(
            "@example.invalid"
        )

        assert writer.endswith(
            "@example.invalid"
        )

        TestStripeAccounting.setUpClass()

        fixture = TestStripeAccounting(
            "test_native_receipt_notification_gate_and_replay"
        )

        fixture.setUp()

        ticket = fixture.issue.name

        bridge = {
            "enabled":True,
            "compatibility_confirmed":True,
            "technician_role":"SS97 Technician",
            "profile_required":False,
            "historical_integration":True,
            "enforce_paid_interventions":True,
            "email_enabled":False,
            "writer_user":writer,
            "cockpit_pilot_enabled":True,
            "business_authorizer":
                "softsystem97.integrations.ticket_bridge."
                "live_authorizer.authorize_ticket_operation"
        }

        frappe.conf.ss97_ticket_bridge = bridge

        frappe.set_user("Guest")

        assert fixture.deliver(
            fixture.event()
        )["ok"]

        frappe.set_user("Administrator")

        assert payment_gate.issue_has_verified_stripe_payment(
            ticket
        )

        print("PAIEMENT FICTIF VERIFIE : OK")

        api.assign_ticket(
            ticket,
            tech["email"],
            "browser154-" + secrets.token_hex(12)
        )

        assert policy.assigned(
            ticket,tech["email"]
        )

        frappe.db.set_value("Issue",ticket,{
            "ss97_ticket_status":
                "Accepté par le technicien",
            "ss97_accepted_on":frappe.utils.now(),
            "ss97_checklist_pre_done":1,
            "ss97_security_suspend":0,
            "ss97_timer_status":"stopped"
        })

        print("AFFECTATION TECHNICIEN : OK")

        admin = (
            "n2-browser-" + secrets.token_hex(8)
            + "@example.invalid"
        )

        password = secrets.token_urlsafe(32) + "!9Aa"

        frappe.get_doc({
            "doctype":"User",
            "email":admin,
            "first_name":"SS97 Browser Audit",
            "enabled":1,
            "user_type":"System User",
            "send_welcome_email":0,
            "roles":[
                {"role":"System Manager"},
                {"role":"Support Team"}
            ]
        }).insert()

        update_password(admin,password)

        frappe.db.commit()

        frappe.flags.in_test = False
        frappe.in_test = False

        def pilot_init(request):

            result = original(request)

            if frappe.local.site != SITE:
                frappe.throw(
                    "Site interdit",
                    frappe.PermissionError
                )

            if frappe.conf.get("ignore_csrf"):
                frappe.throw(
                    "CSRF obligatoire",
                    frappe.PermissionError
                )

            if request.path.startswith((
                "/api/method/softsystem97.integrations."
                "ticket_bridge.cockpit_api.",
                "/api/method/softsystem97.integrations."
                "ticket_bridge.cockpit_admin."
            )):

                frappe.conf.ss97_ticket_bridge = dict(
                    bridge
                )

            return result

        frappe.app.init_request = pilot_init

        frappe.app._site = SITE

        frappe.app._sites_path = str(Path.cwd())

        server = make_server(
            "127.0.0.1",
            0,
            frappe.app.application_with_statics(),
            threaded=True
        )

        thread = threading.Thread(
            target=server.serve_forever,
            daemon=True
        )

        thread.start()

        payload = {
            "base":
                f"http://127.0.0.1:{server.server_port}",
            "ticket":ticket,
            "tech":{
                "email":tech["email"],
                "password":tech["password"]
            },
            "admin":{
                "email":admin,
                "password":password
            }
        }

        print("TICKET DE TEST :",ticket)

        subprocess.run(
            [
                browser_python,
                "-u",
                str(Path(__file__).resolve()),
                "--browser"
            ],
            input=json.dumps(payload),
            text=True,
            check=True,
            timeout=300
        )

        frappe.db.rollback()

        frappe.set_user("Administrator")

        assert frappe.db.get_value(
            "Issue",ticket,"status"
        ) == "Closed"

        assert frappe.db.get_value(
            "Issue",ticket,"ss97_intervention_report"
        )

        assert frappe.db.count("ToDo",{
            "reference_type":"Issue",
            "reference_name":ticket,
            "status":"Open"
        }) == 0

        print("CLOTURE CONFIRMEE EN BASE : OK")
        print("RAPPORT CONSERVE : OK")
        print("AFFECTATIONS RESIDUELLES : ZERO")

    finally:

        if server:
            server.shutdown()
            server.server_close()

        if thread:
            thread.join(timeout=10)

        frappe.app.init_request = original

        frappe.db.rollback()

        frappe.conf.ss97_ticket_bridge = old_config

        if admin:

            frappe.set_user("Administrator")

            if frappe.db.exists("User",admin):

                frappe.db.set_value(
                    "User",admin,"enabled",0
                )

                frappe.db.commit()

                print("COMPTE ADMIN TEST DESACTIVE")

        frappe.destroy()

    print("VALIDATION GRAPHIQUE COMPLETE N2 : OK")


if __name__ == "__main__":

    if sys.argv[1] == "--browser":

        browser_test()

    else:

        integration_test(sys.argv[1])
