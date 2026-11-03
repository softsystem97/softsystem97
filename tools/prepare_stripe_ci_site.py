"""Provision only a fresh disposable local CI site; never a remote Frappe site."""
import json
import os
from pathlib import Path
import secrets

import frappe
from frappe.installer import _new_site


def main():
    bench = Path.cwd()
    if not (bench / 'sites/apps.txt').is_file():
        raise RuntimeError('Run from the disposable bench root')
    if (bench / 'sites/test_stripe').exists():
        raise RuntimeError('Refusing to reuse an existing site')
    os.chdir(bench / 'sites')
    frappe.init('test_stripe', new_site=True)
    _new_site(db_name='test_ss97_stripe', site='test_stripe',
        db_root_username='root', db_root_password=os.environ['SS97_CI_DB_PASSWORD'],
        admin_password=secrets.token_urlsafe(32), install_apps=['erpnext','softsystem97'],
        db_type='mariadb', db_host='127.0.0.1', db_port=3306,
        mariadb_user_host_login_scope='%')
    frappe.destroy()
    config = Path('test_stripe/site_config.json')
    values = json.loads(config.read_text())
    values.update(allow_tests=1, ss97_stripe_test_site=True, STRIPE_MODE='test', PAYMENTS_LIVE_ENABLED=0)
    config.write_text(json.dumps(values))
    assets=Path('assets');assets.mkdir(exist_ok=True)
    (assets/'assets.json').write_text('{}')
    frappe.init('test_stripe');frappe.connect();frappe.set_user('Administrator')
    from erpnext.setup.setup_wizard.operations.install_fixtures import install
    install('France')
    frappe.db.commit();frappe.destroy()


if __name__ == '__main__':
    main()
