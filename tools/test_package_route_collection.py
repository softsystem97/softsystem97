"""Offline packaging checks; does not import Frappe or invoke the collector."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from package_route_collection import build


class TestCollectionBundle(unittest.TestCase):
    def test_exact_allowlist_and_checksums(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "collection.zip"
            manifest = build(output)
            with ZipFile(output) as archive:
                self.assertEqual(set(archive.namelist()), {
                    "ss97_route_metadata.py", "INSTRUCTIONS.md", "consolidated-release.md", "SHA256.json"})
                self.assertEqual(json.loads(archive.read("SHA256.json")), manifest)
                for name, expected in manifest.items():
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), expected)
                compile(archive.read("ss97_route_metadata.py"), "collector", "exec")
            with self.assertRaises(FileExistsError):
                build(output)


if __name__ == "__main__":
    unittest.main()
