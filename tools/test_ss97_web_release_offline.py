"""Offline web-route preflight regression. No Frappe Cloud credentials."""
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from tools.check_ss97_web_release import REQUIRED_FILES, audit_source, audit_wheel


class RoutePreflightTests(unittest.TestCase):
    def test_live_release_source_includes_routes_and_assets(self):
        self.assertTrue(audit_source()["ok"])

    def test_missing_route_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(audit_source(Path(folder))["ok"])

    def test_wheel_missing_asset_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            wheel = Path(folder) / "test.whl"
            with ZipFile(wheel, "w") as archive:
                for file in REQUIRED_FILES[:-1]:
                    archive.writestr(file, "test")
            check = audit_wheel(wheel)
            self.assertFalse(check["ok"])
            self.assertEqual(check["missing"], [REQUIRED_FILES[-1]])


if __name__ == "__main__":
    unittest.main()
