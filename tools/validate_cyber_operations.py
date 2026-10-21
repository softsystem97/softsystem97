"""Repeatable local Cyber validation using an ephemeral queue; no migration or external calls.

Run with the bench Python from the bench directory. Requires an already migrated
allow_tests audit/test site, local redis-server, Playwright/Chromium, aiosmtpd for
--with-regressions. All users/data exercised are synthetic fixtures.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import frappe
from validate_local_mail import isolated_background_queue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True)
    parser.add_argument("--chromium", default="/usr/bin/chromium")
    parser.add_argument("--with-regressions", action="store_true")
    args = parser.parse_args()
    if not args.site.startswith(("audit.", "test_")):
        parser.error("Disposable audit/test site required")
    bench = Path.cwd()
    sites = bench / "sites"
    tools = Path(__file__).resolve().parent
    os.chdir(sites)
    frappe.init(site=args.site, sites_path=str(sites))
    frappe.connect()
    try:
        if not frappe.conf.allow_tests:
            raise RuntimeError("allow_tests required")
        for dt in (
            "SS97 Cyber Report",
            "SS97 Cyber Remote Request",
            "SS97 Cyber Sync Event",
        ):
            if not frappe.db.exists("DocType", dt):
                raise RuntimeError(
                    "Schema missing: perform separately authorized lab migration first"
                )
        commands = [
            ("frappe", "run_local_tests.py", ["--site", args.site]),
            ("http", "validate_cyber_http.py", ["--site", args.site]),
            ("browser", "test_cyber_browser.py", ["--chromium", args.chromium]),
        ]
        if args.with_regressions:
            commands += [
                (
                    "historical",
                    "test_historical_ticket_sources.py",
                    ["--frappe-site", args.site],
                ),
                (
                    "technician-http",
                    "validate_ticket_bridge_http.py",
                    ["--site", args.site],
                ),
                (
                    "technician-browser",
                    "test_ticket_bridge_browser.py",
                    ["--chromium", args.chromium],
                ),
                ("smtp", "validate_local_mail.py", ["--site", args.site, "--bridge"]),
                ("native-smtp", "validate_local_mail.py", ["--site", args.site]),
            ]
        with (
            (bench / "logs/operations-validation-redis.log").open("w") as queue_log,
            isolated_background_queue(queue_log),
        ):
            for name, script, arguments in commands:
                path = bench / "logs" / f"operations-validation-{name}.log"
                with path.open("w") as log:
                    result = subprocess.run(
                        [sys.executable, str(tools / script), *arguments],
                        cwd=bench,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        check=False,
                    )
                print(
                    f"{name}: {'PASS' if result.returncode == 0 else 'FAIL'} — {path}",
                    flush=True,
                )
                if result.returncode:
                    return 1
        return 0
    finally:
        frappe.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
