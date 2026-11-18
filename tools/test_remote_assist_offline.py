"""Run without a Frappe site: python -m unittest tools.test_remote_assist_offline."""

import unittest

from softsystem97.remote.logic import (
    PENDING, TERMINAL, can_transition, code_digest, new_code, normalize_code,
)


class TestRemoteAssistLogic(unittest.TestCase):
    secret = "A" * 48

    def test_generated_code_is_nine_ascii_digits(self):
        values = {new_code() for _ in range(200)}
        self.assertEqual(len(values), 200)
        for code in values:
            self.assertRegex(code, r"^[1-9][0-9]{8}$")

    def test_code_strict_input(self):
        for invalid in (123456789, None, "12345678", "1234567890", "１２３４５６７８９",
                        "123-456-789", " 123456789", "123456789\n", True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                normalize_code(invalid)
        self.assertEqual(normalize_code("123456789"), "123456789")

    def test_digest_is_keyed_and_does_not_store_plain_code(self):
        first = code_digest("123456789", self.secret)
        self.assertEqual(first, code_digest("123456789", self.secret))
        self.assertNotIn("123456789", first)
        self.assertNotEqual(first, code_digest("123456789", "B" * 48))
        self.assertNotEqual(first, code_digest("223456789", self.secret))

    def test_missing_weak_secret_is_denied(self):
        for invalid in (None, "", "short", 123):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                code_digest("123456789", invalid)

    def test_allowed_preparation_and_expiration(self):
        self.assertTrue(can_transition("CREATED", "CLIENT_READY"))
        self.assertTrue(can_transition("CLIENT_READY", "CLIENT_APPROVED"))
        for state in PENDING:
            self.assertTrue(can_transition(state, "ENDED"))
            self.assertTrue(can_transition(state, "EXPIRED"))

    def test_no_frontend_path_can_mark_remote_active(self):
        for state in PENDING | TERMINAL | {"ACTIVE"}:
            self.assertFalse(can_transition(state, "ACTIVE"))
        self.assertFalse(can_transition("DECLINED", "CLIENT_APPROVED"))
        self.assertFalse(can_transition("ENDED", "CLIENT_READY"))
        self.assertFalse(can_transition("EXPIRED", "CLIENT_READY"))

    def test_declined_is_terminal_and_active_can_end(self):
        self.assertTrue(can_transition("CLIENT_READY", "DECLINED"))
        self.assertTrue(can_transition("ACTIVE", "ENDED"))
        for state in TERMINAL:
            for target in ("CLIENT_READY", "CLIENT_APPROVED", "CREATED"):
                self.assertFalse(can_transition(state, target))


if __name__ == "__main__":
    unittest.main()
