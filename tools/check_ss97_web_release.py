"""Preflight Frappe Cloud 404 diagnosis: no secrets, no production writes.

Validate that the release includes the two private/business routes and their
public scripts in the source tree and in a built Python wheel. Optional
read-only remote probe can be used AFTER deploying a private bench/site.
"""
import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
ROUTES = (
    "ss97-cyberos",
    "ss97-tech-cyber",
    "ss97-cyber-entreprises",
)
ASSETS = (
    "ss97_cyberos.js",
    "ss97_cyberos_v2.js",
    "ss97_cyberos_v3.js",
    "ss97_n4_dashboard.js",
)
REQUIRED_FILES = tuple(
    "softsystem97/www/" + route + ext
    for route in ROUTES for ext in (".html", ".py")
) + tuple(
    "softsystem97/public/js/" + asset for asset in ASSETS
)


def audit_source(root=ROOT):
    missing = [name for name in REQUIRED_FILES if not (root / name).is_file()]
    return {"ok": not missing, "checked": len(REQUIRED_FILES), "missing": missing}


def audit_wheel(path):
    with ZipFile(path) as archive:
        present = set(archive.namelist())
    missing = [name for name in REQUIRED_FILES if name not in present]
    return {"ok": not missing, "wheel": str(path), "checked": len(REQUIRED_FILES),
            "missing": missing}


def remote_probe(site):
    """Probe only user-facing GET routes; never credentials or API writes."""
    parts = urlsplit(site)
    if parts.scheme != "https" or not parts.netloc or parts.username or parts.password:
        raise ValueError("Adresse HTTPS valide obligatoire.")
    origin = parts.scheme + "://" + parts.netloc
    paths = ["/ss97-cyberos", "/ss97-tech-cyber", "/ss97-cyber-entreprises"]
    paths.extend("/assets/softsystem97/js/" + file for file in ASSETS)
    output = {}
    for path in paths:
        request = Request(origin + path, headers={"User-Agent": "SS97-read-only-deploy-preflight/1"})
        try:
            with urlopen(request, timeout=12) as response:
                output[path] = {"status": response.status,
                    "final_url": response.geturl(), "type": response.headers.get("Content-Type", "")}
        except HTTPError as exc:
            output[path] = {"status": exc.code, "error": "HTTP response"}
        except (OSError, URLError) as exc:
            output[path] = {"status": "UNREACHABLE", "error": type(exc).__name__}
    warning = (
        "A 404 for protected /ss97-tech-cyber MAY be a permission/guest response; "
        "repeat as an authorized N4. A 404 for public /ss97-cyberos or its "
        "JavaScript means the deployed bench/site version must be checked."
    )
    return {"site": origin, "results": output, "warning": warning}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path, help="Previously built .whl file")
    parser.add_argument("--site", help="Optional read-only HTTPS target")
    args = parser.parse_args()
    result = {"source": audit_source()}
    if args.wheel:
        result["wheel"] = audit_wheel(args.wheel)
    if args.site:
        result["remote"] = remote_probe(args.site)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["source"]["ok"] or (args.wheel and not result["wheel"]["ok"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
