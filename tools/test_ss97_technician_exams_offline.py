"""No Frappe site or private question bank is contacted in these tests."""

import json
import unittest
from datetime import datetime, timedelta

from softsystem97.technician_exams.rules import (
    TRACKS, grade, public_questions, seconds_remaining, track_for,
    validate_question,
)


def snapshot_for(track, critical=False):
    return [{"id": f"Q{i:03d}", "prompt": f"Question complète n° {i}",
             "category": "Pratique", "options": {"A": "Un", "B": "Deux", "C": "Trois", "D": "Quatre"},
             "correct_option": "B", "critical": critical and i == 0}
            for i in range(TRACKS[track].question_count)]


class TechnicianExamRulesTests(unittest.TestCase):
    def test_exact_counts_and_times(self):
        self.assertEqual([(x.question_count, x.minutes, x.required_correct)
                          for x in TRACKS.values()], [(20, 20, 14), (30, 25, 24), (40, 20, 34)])

    def test_invalid_track(self):
        for code in ("L5", "L3", "", None, 3):
            with self.subTest(code=code), self.assertRaises(ValueError):
                track_for(code)

    def test_question_bank_validated(self):
        opts = json.dumps({"A": "a", "B": "b", "C": "c", "D": "d"})
        self.assertEqual(validate_question("Quel est le diagnostic ?", opts, "C")["C"], "c")
        for bad in ("{}", "[]", "not json", '{"A":"a"}'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_question("Quel est le diagnostic ?", bad, "A")

    def test_answer_keys_never_in_client_payload(self):
        payload = public_questions(snapshot_for("L2", critical=True))
        text = json.dumps(payload)
        self.assertNotIn("correct_option", text)
        self.assertNotIn("critical", text)

    def test_threshold_for_each_track(self):
        for key, settings in TRACKS.items():
            with self.subTest(track=key):
                questions = snapshot_for(key)
                passed = {q["id"]: ("B" if i < settings.required_correct else "A")
                          for i, q in enumerate(questions)}
                self.assertTrue(grade(key, questions, passed)["passed"])
                passed[questions[0]["id"]] = "A"
                self.assertFalse(grade(key, questions, passed)["passed"])

    def test_critical_miss_blocks_even_with_high_score(self):
        questions = snapshot_for("CYBER", critical=True)
        answers = {q["id"]: "B" for q in questions}
        answers[questions[0]["id"]] = "A"
        result = grade("CYBER", questions, answers)
        self.assertEqual(result["correct"], 39)
        self.assertEqual(result["critical_errors"], 1)
        self.assertFalse(result["passed"])

    def test_incomplete_exam_and_forged_answer_refused(self):
        questions = snapshot_for("BANK")
        with self.assertRaises(ValueError):
            grade("BANK", questions[:-1], {})
        with self.assertRaises(ValueError):
            grade("BANK", questions, {"Q999": "A"})
        with self.assertRaises(ValueError):
            grade("BANK", questions, {"Q000": "E"})

    def test_server_clock_is_authoritative(self):
        now = datetime(2026, 11, 18, 12, 0, 0)
        self.assertEqual(seconds_remaining(now + timedelta(minutes=20), now), 1200)
        self.assertEqual(seconds_remaining(now - timedelta(seconds=1), now), 0)


if __name__ == "__main__":
    unittest.main()
