"""Synthetic regression tests. Real answers never enter the public repository."""
import csv
import io
import unittest
from pathlib import Path
from softsystem97.technician_exams.private_import_rules import COLUMNS, check_n4_csv

ROOT = Path(__file__).resolve().parents[1]

def batch(count=40, active="0", duplicate=False):
    out=io.StringIO()
    writer=csv.DictWriter(out,fieldnames=COLUMNS)
    writer.writeheader()
    for i in range(count):
        prompt=f"Question synthétique de validation numéro {0 if duplicate else i:02d} ?"
        writer.writerow({"track":"CYBER", "category":"Sécurité",
            "prompt":prompt,
            "options_json":'{"A":"Première","B":"Deuxième","C":"Troisième","D":"Quatrième"}',
            "correct_option":"A","critical":"0","is_active":active})
    return out.getvalue().encode()

class N4PrivateImportTests(unittest.TestCase):
    def test_40_inactive_questions(self):
        result=check_n4_csv(batch())
        self.assertEqual(len(result["questions"]),40)
        self.assertTrue(all(row["is_active"]==0 for row in result["questions"]))
    def test_never_allow_activation(self):
        with self.assertRaises(ValueError): check_n4_csv(batch(active="1"))
    def test_exact_count(self):
        for number in (0,39,41):
            with self.assertRaises(ValueError): check_n4_csv(batch(count=number))
    def test_no_duplicates(self):
        with self.assertRaises(ValueError): check_n4_csv(batch(duplicate=True))
    def test_invalid_input(self):
        for raw in (b"",b"bogus",b"\xff",b"a"*200001):
            with self.assertRaises(ValueError): check_n4_csv(raw)
    def test_manager_only_private_and_no_commit(self):
        src=(ROOT/"softsystem97/technician_exams/private_import.py").read_text()
        js=(ROOT/"softsystem97/public/js/ss97_n4_import.js").read_text()
        self.assertIn('"System Manager" not in frappe.get_roles(manager)',src)
        self.assertIn('doc.is_active = 0',src)
        self.assertIn('"track": "CYBER"',src)
        self.assertIn('meta.owner != manager',src)
        self.assertNotIn('frappe.db.commit(',src)
        self.assertNotIn("innerHTML",js)
        self.assertNotIn("correct_option",js)
if __name__ == "__main__":
    unittest.main()
