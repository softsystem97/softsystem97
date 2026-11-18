"""Read-only exam preflight: no private questions or answer keys are published."""

import json
import unittest

from softsystem97.technician_exams.readiness import audit_bank


def question(prompt):
    return {"prompt": prompt,
            "options_json": json.dumps({"A": "Démarrer", "B": "Arrêter",
                                         "C": "Installer", "D": "Vérifier"}),
            "correct_option": "D", "category": "Sécurité"}


class ExamBankAuditTests(unittest.TestCase):
    def test_valid_bank_ready_without_exposing_answers(self):
        rows = [question(f"Quelle est la bonne vérification numéro {i} ?")
                for i in range(20)]
        result = audit_bank(rows, required=20)
        self.assertEqual(result, {"active_count": 20, "invalid_count": 0,
                                  "duplicate_count": 0, "ready": True})
        self.assertNotIn("correct_option", result)
        self.assertNotIn("prompt", result)

    def test_broken_answer_key_blocks_opening_even_when_count_ok(self):
        rows = [question(f"Quelle vérification effectuer numéro {i} ?")
                for i in range(30)]
        rows[5]["correct_option"] = "E"
        result = audit_bank(rows, required=30)
        self.assertFalse(result["ready"])
        self.assertEqual(result["invalid_count"], 1)

    def test_duplicate_questions_block_opening(self):
        rows = [question(f"Question différente numéro {i} à auditer")
                for i in range(40)]
        rows[3]["prompt"] = "  QUESTION   différente numéro 2  à AUDITER "
        result = audit_bank(rows, required=40)
        self.assertFalse(result["ready"])
        self.assertEqual(result["duplicate_count"], 1)

    def test_incomplete_bank_never_ready(self):
        self.assertFalse(audit_bank([question("Question de test complète")], 20)["ready"])

    def test_oversized_bank_matches_exam_limit(self):
        rows = [question(f"Question de contrôle sécurité numéro {i}")
                for i in range(501)]
        result = audit_bank(rows, required=40, total=501)
        self.assertFalse(result["ready"])

    def test_truncated_bank_is_not_ready(self):
        rows = [question(f"Question de contrôle sécurité numéro {i}")
                for i in range(40)]
        self.assertFalse(audit_bank(rows, required=40, total=50)["ready"])


if __name__ == "__main__":
    unittest.main()
