"""Offline regression tests for the N4 active question-bank exam-start gate.

No private question text or answer keys are committed. No Frappe site is contacted.
"""
import ast
import json
import unittest
from pathlib import Path

from softsystem97.technician_exams.readiness import audit_bank

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "softsystem97" / "technician_exams" / "api.py"


def synthetic_question(i):
    return {
        "prompt": f"Quelle vérification de sécurité fictive faut-il effectuer à l'étape numéro {i:02d} ?",
        "category": "Contrôle fictif",
        "options_json": json.dumps(
            {"A": "Contrôler", "B": "Réévaluer", "C": "Confirmer", "D": "Documenter"}
        ),
        "correct_option": "D",
        "critical": 1 if i < 18 else 0,
    }


class N4ActiveBankGateTests(unittest.TestCase):
    def test_exactly_forty_unique_valid_active_rows_are_ready(self):
        rows = [synthetic_question(i) for i in range(40)]
        self.assertEqual(audit_bank(rows, 40), {
            "active_count": 40, "invalid_count": 0,
            "duplicate_count": 0, "ready": True,
        })

    def test_less_than_forty_cannot_start(self):
        self.assertFalse(audit_bank([synthetic_question(i) for i in range(39)], 40)["ready"])

    def test_duplicate_blocks_even_if_count_is_forty(self):
        rows = [synthetic_question(i) for i in range(40)]
        rows[-1]["prompt"] = "  " + rows[0]["prompt"].upper() + "  "
        result = audit_bank(rows, 40)
        self.assertFalse(result["ready"])
        self.assertEqual(result["duplicate_count"], 1)

    def test_invalid_answer_key_blocks_even_if_count_is_forty(self):
        rows = [synthetic_question(i) for i in range(40)]
        rows[39]["correct_option"] = "E"
        result = audit_bank(rows, 40)
        self.assertFalse(result["ready"])
        self.assertEqual(result["invalid_count"], 1)

    def test_truncated_or_oversized_bank_blocks(self):
        rows = [synthetic_question(i) for i in range(40)]
        self.assertFalse(audit_bank(rows, 40, total=41)["ready"])
        self.assertFalse(audit_bank(rows, 40, total=501)["ready"])

    def test_audit_never_returns_private_answers_or_prompts(self):
        rows = [synthetic_question(i) for i in range(40)]
        output = audit_bank(rows, 40)
        self.assertEqual(set(output), {
            "active_count", "invalid_count", "duplicate_count", "ready"
        })
        self.assertNotIn(rows[0]["prompt"], json.dumps(output))
        self.assertNotIn("correct_option", json.dumps(output))

    def test_start_exam_audits_all_active_rows_before_sample(self):
        source = API.read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        body = ast.get_source_segment(source, functions["start_exam"])
        self.assertIn("bank_audit = audit_bank(rows, required=settings.question_count)", body)
        self.assertIn('if not bank_audit["ready"]:', body)
        self.assertLess(body.index("bank_audit = audit_bank("),
                        body.index("secrets.SystemRandom().sample(rows, settings.question_count)"))
        self.assertIn('filters={"track": track, "is_active": 1}', body)
        self.assertNotIn("ignore_permissions=True", body.split("chosen =")[0])


if __name__ == "__main__":
    unittest.main()
