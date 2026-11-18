"""Offline tests: taxpayer configuration must never be guessed."""
import unittest
from decimal import Decimal

from softsystem97.intelligence.billing_rules import (
    exact_eur, validate_billing_settings, validate_inclusive_taxes,
)


class TestIntelligenceBillingRules(unittest.TestCase):
    def test_amounts_are_cents_exact(self):
        self.assertEqual(exact_eur("149.00"), Decimal("149.00"))
        for value in (None, "", True, "NaN", "Infinity", "-1", "0", "1.001", "999999999"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                exact_eur(value)

    def test_explicit_tax_template_or_exemption(self):
        base = {"company": "SS97", "item_code": "SERVICE"}
        with self.assertRaises(ValueError):
            validate_billing_settings(base)
        self.assertEqual(validate_billing_settings({**base, "tax_exempt": True})["company"], "SS97")
        self.assertEqual(validate_billing_settings({**base, "tax_template": "TAX"})["tax_template"], "TAX")
        with self.assertRaises(ValueError):
            validate_billing_settings({**base, "tax_template": "TAX", "tax_exempt": True})
        with self.assertRaises(ValueError):
            validate_billing_settings({**base, "tax_exempt": True, "secret": "wrong"})

    def test_inclusive_tax_only(self):
        valid = [{"charge_type": "On Net Total", "included_in_print_rate": 1,
                  "add_deduct_tax": "Add", "account_head": "TVA"}]
        self.assertTrue(validate_inclusive_taxes(valid))
        for rows in ([], [{**valid[0], "included_in_print_rate": 0}],
                     [{**valid[0], "charge_type": "On Previous Row Amount"}],
                     [{**valid[0], "account_head": None}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                validate_inclusive_taxes(rows)


if __name__ == "__main__":
    unittest.main()
