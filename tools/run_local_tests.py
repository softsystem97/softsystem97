"""Run the focused integration suite from a disposable Frappe bench directory."""
import argparse
import os
from pathlib import Path
import unittest

import frappe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', required=True)
    args = parser.parse_args()
    if not args.site.startswith(('audit.', 'test_')):
        parser.error('Only disposable audit/test sites are accepted')
    sites = Path.cwd() / 'sites'
    os.chdir(sites)
    frappe.init(site=args.site, sites_path=str(sites))
    frappe.connect()
    if not frappe.conf.allow_tests:
        raise RuntimeError('allow_tests required')
    frappe.flags.in_test = True
    old_in_test = frappe.in_test
    frappe.in_test = True
    try:
        suite = unittest.defaultTestLoader.loadTestsFromNames([
            'softsystem97.tests.test_access', 'softsystem97.tests.test_mail_queue',
            'softsystem97.tests.test_api_helpers', 'softsystem97.tests.test_provisioning',
            'softsystem97.tests.test_ticket_bridge'])
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    finally:
        frappe.in_test = old_in_test
        frappe.destroy()


if __name__ == '__main__':
    raise SystemExit(main())
