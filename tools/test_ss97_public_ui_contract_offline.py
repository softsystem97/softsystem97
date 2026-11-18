"""Public-facing safety contracts for the TECH OS and cyber pilot UI.

These fast checks do not replace authenticated Frappe integration tests.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1] / "softsystem97"


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


class PublicUiContracts(unittest.TestCase):
    def test_admin_controls_wait_for_server_authorization(self):
        html = source("www/ss97-tech-admin.html")
        js = source("public/js/ss97_tech_admin.js")
        self.assertIn('<div id="admin-protected" hidden>', html)
        self.assertLess(html.index('id="admin-protected"'),
                        html.index('id="admin-review-form"'))
        self.assertLess(js.index('await api("get_admin_overview")'),
                        js.index('$("admin-protected").hidden = false'))

    def test_candidate_entry_explains_separate_recruitment(self):
        html = source("www/ss97-tech-os.html")
        self.assertIn('href="/recrutement"', html)
        self.assertIn('href="/login?redirect-to=%2Fss97-tech-os#signup"', html)
        self.assertIn("Une candidature générale ne crée pas automatiquement", html)

    def test_cyber_submit_remains_disabled_before_approval(self):
        html = source("www/ss97-cyber-entreprises.html")
        js = source("public/js/ss97_cyber_enterprises.js")
        self.assertIn('id="cyber-submit" type="submit" disabled', html)
        self.assertIn('catalogActive = payload.active === true', js)
        self.assertIn('if (!catalogActive)', js)
        self.assertIn('finally {button.disabled = !catalogActive;}', js)

    def test_headings_remain_legible_on_dark_site_theme(self):
        for file in ("public/css/ss97_tech_universe.css", "www/ss97-tech-os.html"):
            with self.subTest(file=file):
                css = source(file)
                self.assertIn("background:#f7f9fc", css)
                self.assertIn("color:#162b43", css)

    def test_static_assets_have_a_release_cache_key(self):
        for file in (
            "www/ss97-cyber-entreprises.html", "www/ss97-tech-admin.html",
            "www/ss97-tech-n2.html", "www/ss97-tech-banque.html",
            "www/ss97-tech-cyber.html",
        ):
            with self.subTest(file=file):
                self.assertIn("ss97_tech_universe.css?v=20261118-r2", source(file))
        self.assertIn("ss97_tech_admin.js?v=20261118-r4", source("www/ss97-tech-admin.html"))

    def test_readiness_is_manager_only_and_never_enables_flags(self):
        page = source("www/ss97-tech-readiness.py")
        html = source("www/ss97-tech-readiness.html")
        js = source("public/js/ss97_tech_readiness.js")
        self.assertIn("_manager()", page)
        self.assertNotIn("_enabled()", page)
        self.assertIn("get_admin_readiness", js)
        self.assertNotIn('method: "POST"', js)
        self.assertNotIn("site_config", js)
        self.assertIn("Aucun bouton sur cette page n'active un service", html)

    def test_customer_can_review_only_own_ticket_from_separate_page(self):
        html = source("www/ss97-client-missions.html")
        page = source("www/ss97-client-missions.py")
        js = source("public/js/ss97_client_missions.js")
        api = source("technician_os/api.py")
        self.assertIn("context.is_guest", page)
        self.assertIn("{% if is_guest %}", html)
        self.assertIn("/login?redirect-to=%2Fss97-client-missions", html)
        self.assertIn('api("get_client_missions"', js)
        self.assertIn('api("review_client_report"', js)
        self.assertIn("dispute_reason: reason", js)
        self.assertIn("window.confirm(prompt)", js)
        self.assertIn("element.textContent = String(value)", js)
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("offered_fee_eur", js)
        self.assertIn('policy.authorize(ticket, "client")', api)
        self.assertIn("_authorized_ticket(mission, \"client\")", api)

    def test_customer_link_and_email_readiness_have_fresh_assets(self):
        cyber_page = source("www/ss97-cyber-entreprises.html")
        ready_page = source("www/ss97-tech-readiness.html")
        ready_js = source("public/js/ss97_tech_readiness.js")
        self.assertIn('href="/ss97-client-missions"', cyber_page)
        self.assertIn("ss97_tech_readiness.js?v=20261118-r3", ready_page)
        self.assertIn("technician_email_enabled", ready_js)
        self.assertIn("technician_schema_ready", ready_js)

    def test_dispute_rework_is_a_separate_sensitive_approval(self):
        admin_js = source("public/js/ss97_tech_admin.js")
        client_js = source("public/js/ss97_client_missions.js")
        api = source("technician_os/api.py")
        self.assertIn('api("request_dispute_rework"', admin_js)
        self.assertIn('api("approve_sensitive_rework"', admin_js)
        self.assertIn("REWORK_PENDING_APPROVAL", client_js)
        self.assertIn('def request_dispute_rework(', api)
        self.assertIn('def approve_sensitive_rework(', api)
        self.assertIn('mission.rework_authorization_reference', api)
        self.assertIn('mission.rework_requested_by', api)
        self.assertNotIn("stripe.Transfer.create", api)


if __name__ == "__main__":
    unittest.main()
