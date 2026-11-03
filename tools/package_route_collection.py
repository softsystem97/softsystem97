"""Build a reviewable metadata-only administrator bundle; no server connection."""

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def build(output):
    root = Path(__file__).resolve().parents[1]
    files = {
        "ss97_route_metadata.py": root / "softsystem97/route_metadata.py",
        "INSTRUCTIONS.md": root / "docs/route-metadata-collection.md",
        "consolidated-release.md": root / "docs/consolidated-release.md",
    }
    payloads = {name: path.read_bytes() for name, path in files.items()}
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()}
    with ZipFile(output, "x", ZIP_DEFLATED) as archive:
        for name, data in payloads.items():
            archive.writestr(name, data)
        archive.writestr("SHA256.json", json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    print(json.dumps(build(parser.parse_args().output), indent=2))
