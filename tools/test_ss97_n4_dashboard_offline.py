"""N4 cyber dashboard: aggregate and least-privilege static regression checks."""
import unittest
from pathlib import Path
from softsystem97.technician_os.cyber_dashboard_rules import summarize

ROOT=Path(__file__).resolve().parents[1]

class N4DashboardTests(unittest.TestCase):
    def test_counts_are_scoped_to_authorized_missions(self):
        entries=[{"state":"OFFERED"},{"state":"IN_PROGRESS"},
                 {"state":"REPORT_SUBMITTED"},{"state":"CLIENT_ACCEPTED"},
                 {"state":"DISPUTED"},{"state":"REWORK_PENDING_APPROVAL"}]
        result=summarize(entries)
        self.assertEqual(result["total"],6)
        self.assertEqual(result["in_progress"],1)
        self.assertEqual(result["reports"],1)
        self.assertEqual(result["closed"],1)
        self.assertEqual(result["disputed"],2)

    def test_no_tasks_is_zero(self):
        self.assertEqual(summarize([])["total"],0)

    def test_security_gates_in_dashboard(self):
        api=(ROOT/"softsystem97/technician_os/cyber_dashboard.py").read_text()
        for condition in ['_my_active_profile()', 'profile.track != "CYBER"',
                          '_authorized_ticket(mission, "technician")',
                          "mission.authorization_reference", "mission.approved_by",
                          "ticket.status == \"Closed\""]:
            self.assertIn(condition,api)
        self.assertNotIn("ignore_permissions=True",api)
        self.assertNotIn("@frappe.whitelist(methods=[\"POST\"])",api)

    def test_frontend_is_safe(self):
        js=(ROOT/"softsystem97/public/js/ss97_n4_dashboard.js").read_text()
        html=(ROOT/"softsystem97/www/ss97-tech-cyber.html").read_text()
        self.assertIn("textContent",js)
        self.assertNotIn("innerHTML",js)
        self.assertIn("ss97_n4_dashboard.js",html)
        self.assertIn("n4-command-profile",html)
