"""Static safety contracts for the privileged bridge preflight."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class BridgeReadinessTests(unittest.TestCase):
    def test_admin_gate_and_no_mutating_apis(self):
        text=(ROOT/"softsystem97/integrations/ticket_bridge/readiness.py").read_text()
        self.assertIn('"System Manager" not in frappe.get_roles(user)',text)
        self.assertIn('@frappe.whitelist(methods=["GET"])',text)
        self.assertIn('"no_active_issue_workflow"',text)
        self.assertIn('"service_writer_configured"',text)
        self.assertIn('cfg.get("profile_required") is False',text)
        self.assertNotIn('ignore_permissions=True',text)
        self.assertNotIn("frappe.db.set_value(",text)
        self.assertNotIn('methods=["POST"]',text)
    def test_ui_escapes_text_and_never_activates_bridge(self):
        script=(ROOT/"softsystem97/public/js/ss97_bridge_readiness.js").read_text()
        page=(ROOT/"softsystem97/www/ss97-tech-admin.html").read_text()
        self.assertIn("textContent",script)
        self.assertNotIn("innerHTML",script)
        self.assertNotIn('method:"POST"',script)
        self.assertIn("ss97_bridge_readiness.js",page)

if __name__=="__main__": unittest.main()
