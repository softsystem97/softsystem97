"""Pure domain tests; do not require a live DB, Stripe or an external model."""
import unittest

from softsystem97.intelligence.catalog import catalog, offer
from softsystem97.intelligence.engine import build_assessment, parse_answers


class TestIntelligenceEngine(unittest.TestCase):
    def setUp(self):
        self.answers = {"objective": "Améliorer la rentabilité",
                        "challenges": "Coûts élevés", "revenue_eur": "120000",
                        "costs_eur": "99000"}

    def test_all_tracks_three_tiers(self):
        self.assertEqual(len(catalog()), 15)
        self.assertEqual(offer("cyber", "expert")["price_eur"], "1490.00")
        with self.assertRaises(ValueError):
            offer("secret", "expert")

    def test_unknown_sector_and_all_tiers(self):
        for tier, size in (("basic", 5), ("advanced", 8), ("expert", 12)):
            with self.subTest(tier=tier):
                output = build_assessment("Atelier 1", "Métier non catalogué", "business", tier, self.answers)
                self.assertEqual(len(output["actions"]), size)
                self.assertEqual(len({a["id"] for a in output["actions"]}), size)

    def test_finance_is_only_illustrative_and_opt_in(self):
        basic = build_assessment("A", "Commerce", "business", "basic", self.answers)
        self.assertIsNone(basic["scenarios"])
        advanced = build_assessment("A", "Commerce", "business", "advanced", self.answers)
        self.assertEqual(len(advanced["scenarios"]["scenarios"]), 3)
        del self.answers["costs_eur"]
        missing = build_assessment("A", "Commerce", "business", "expert", self.answers)
        self.assertIsNone(missing["scenarios"])

    def test_invalid_inputs_rejected(self):
        for data in ('{"objective":1}', {"objective": "a", "challenges": "b", "extra": "bad"},
                     {"objective": "a", "challenges": "b", "revenue_eur": "-10"}):
            with self.assertRaises(ValueError):
                parse_answers(data)
        with self.assertRaises(ValueError):
            build_assessment("X", "Commerce", "cyber", "premium", self.answers)


if __name__ == "__main__":
    unittest.main()
