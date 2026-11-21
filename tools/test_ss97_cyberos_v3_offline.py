"""Regression tests for the CyberDirector deterministic calculations."""
import unittest
from pathlib import Path
from softsystem97.cyberos.advisory_logic import disruption_estimate,advisory
from softsystem97.cyber_assessment.catalog import QUESTIONS

ROOT=Path(__file__).resolve().parents[1]

class DirectorTests(unittest.TestCase):
 def test_decimal(self):
  self.assertEqual(disruption_estimate("4.5","150.20","10.10")["total_eur"],"686.00")
 def test_invalid_amounts(self):
  for value in ("NaN","Infinity","-1","1000000000","1.999"):
   with self.assertRaises(ValueError): disruption_estimate(value,"10","0")
 def test_reject_float(self):
  with self.assertRaises(ValueError): disruption_estimate(1.2,"10","0")
 def test_advice_is_never_certification(self):
  data=advisory({key:"YES" for key in QUESTIONS})
  self.assertEqual(len(data["controls"]),10)
  self.assertTrue(all(not item["verified"] for item in data["controls"]))
 def test_api_customer_scoped(self):
  source=(ROOT/"softsystem97/cyberos/advisory_api.py").read_text()
  self.assertIn("_company()",source)
  self.assertIn('policy.authorize(issue,"client")',source)
  self.assertIn('"customer":customer,"customer_user":user',source)
 def test_no_html_injection(self):
  source=(ROOT/"softsystem97/public/js/ss97_cyberos_v3.js").read_text()
  self.assertNotIn("innerHTML",source)
  self.assertIn("textContent",source)
