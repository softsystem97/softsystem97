"""Exercise real Frappe WSGI login/session/CSRF on an isolated audit/test site.

Uses synthetic fixture users only, with a random in-memory local test password.
No production connection, persistent activation, password output or CSRF bypass.
"""
import argparse
import copy
import os
from pathlib import Path
import re
import secrets
from unittest.mock import patch

import frappe
from werkzeug.test import Client
from werkzeug.wrappers import Response

from softsystem97.integrations.ticket_bridge import api
from softsystem97.tests.test_ticket_bridge import TestTicketBridge


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', required=True)
    args = parser.parse_args()
    if not args.site.startswith(('audit.', 'test_')):
        parser.error('Disposable audit/test site required')
    sites = str(Path.cwd() / 'sites')
    os.chdir(sites)
    from frappe import app as frappe_app
    def connect():
        frappe.init(site=args.site, sites_path=sites)
        frappe.connect()
        frappe.set_user('Administrator')
    connect()
    if not frappe.conf.allow_tests:
        raise RuntimeError('allow_tests required')
    if frappe.conf.get('ignore_csrf'):
        raise RuntimeError('Refusing to test with CSRF protection disabled')
    old_app_site, old_sites_path = frappe_app._site, frappe_app._sites_path
    original_init = frappe_app.init_request
    fixtures = False
    ticket = None
    fixture_issues = []
    count = 0
    def passed(label):
        nonlocal count
        count += 1
        print('PASS ' + label, flush=True)
    try:
        TestTicketBridge.setUpClass()
        fixtures = True
        config = dict(enabled=True, compatibility_confirmed=True,
            technician_role=TestTicketBridge.role, profile_required=False, email_enabled=False)
        frappe.conf.ss97_ticket_bridge = config.copy()
        frappe.set_user(TestTicketBridge.client)
        ticket = api.create_ticket('HTTP controlled Issue', 'Synthetic HTTP fixture', 'http-create')
        fixture_issues.append(ticket['name'])
        frappe.set_user(TestTicketBridge.other)
        foreign_ticket = api.create_ticket('HTTP other customer Issue', 'Synthetic isolation fixture', 'http-other')
        fixture_issues.append(foreign_ticket['name'])
        frappe.set_user('Administrator')
        api.assign_ticket(ticket['name'], TestTicketBridge.tech, 'http-assign')
        # Role without Desk access is deliberately tested as a Website User.
        tech = frappe.get_doc('User', TestTicketBridge.tech)
        tech.user_type = 'Website User'
        tech.save()
        from frappe.utils.password import update_password
        password = secrets.token_urlsafe(32)
        update_password(tech.name, password)
        frappe.db.commit()
        frappe.destroy()
        frappe_app._site, frappe_app._sites_path = args.site, sites
        def init_request(request):
            original_init(request)
            # Opt-in only in the test request context, never site_config or auth internals.
            frappe.conf.ss97_ticket_bridge = copy.deepcopy(config)
        with patch.object(frappe.app, 'init_request', side_effect=init_request):
            client = Client(frappe_app.application, Response)
            base = 'https://audit.localhost'
            prefix = '/api/method/softsystem97.integrations.ticket_bridge.api.'
            def call(method, path, **kwargs):
                response = client.open(path, method=method, base_url=base, buffered=True, **kwargs)
                response.close()
                return response
            config['enabled'] = False
            unavailable = call('GET', '/ss97-dev-technician')
            assert unavailable.status_code == 404, unavailable.status_code
            passed('Disabled development page returns 404 through native router')
            config['enabled'] = True
            guest_page = call('GET', '/ss97-dev-technician')
            assert guest_page.status_code == 200, guest_page.status_code
            assert 'id="ss97-login"' in guest_page.get_data(as_text=True)
            passed('Enabled development page renders login form for anonymous visitor')
            guest = call('GET', prefix + 'list_tickets')
            assert guest.status_code == 403, guest.status_code
            passed('Anonymous request denied by real HTTP dispatcher')
            login = call('POST', '/api/method/login', data={'usr': tech.name, 'pwd': password})
            assert login.status_code == 200, login.status_code
            assert login.json['message'] == 'No App', 'Expected native Website User success response'
            passed('Native Website User password login succeeds with No App response')
            identity = call('GET', '/api/method/frappe.auth.get_logged_user')
            assert identity.status_code == 200 and identity.json['message'] == tech.name
            passed('Session cookie resumes authenticated user across HTTP requests')
            page = call('GET', '/ss97-dev-technician')
            assert page.status_code == 200, page.status_code
            body = page.get_data(as_text=True)
            assert 'ss97-workspace' in body and 'ss97-login' not in body
            token = re.search(r'frappe\.csrf_token\s*=\s*[\"\x27]([^\"\x27]+)', body)
            assert token and token.group(1) not in {'None', 'undefined', ''}, 'Native CSRF token required'
            assert 'no-store' in page.headers.get('Cache-Control', '')
            passed('Real Jinja development page renders authenticated workspace without cache')
            listing = call('GET', prefix + 'list_tickets')
            assert listing.status_code == 200, listing.status_code
            assert [row['name'] for row in listing.json['message']['tickets']] == [ticket['name']]
            passed('Cookie-authenticated technician loads only assigned Issue')
            denied = call('POST', prefix + 'add_intervention', data={
                'name': ticket['name'], 'content': 'Must not persist', 'request_id': 'csrf-denied'})
            assert denied.status_code in {400, 403}, denied.status_code
            passed('Mutation without CSRF token is rejected by native Frappe protection')
            forbidden_get = call('GET', prefix + 'update_status', query_string={
                'name': ticket['name'], 'status': 'Resolved',
                'expected_modified': ticket['modified'], 'request_id': 'get-denied'})
            assert forbidden_get.status_code == 403, forbidden_get.status_code
            passed('Mutation over GET is rejected by real HTTP method enforcement')
            headers = {'X-Frappe-CSRF-Token': token.group(1)}
            comment = call('POST', prefix + 'add_intervention', headers=headers, data={
                'name': ticket['name'], 'content': 'Controlled HTTP intervention', 'request_id': 'http-comment'})
            assert comment.status_code == 200, comment.status_code
            passed('Authorized intervention succeeds over POST with native session and CSRF')
            detail = call('GET', prefix + 'get_ticket', query_string={'name': ticket['name']})
            update = dict(name=ticket['name'], status='Resolved', request_id='http-resolve',
                          expected_modified=detail.json['message']['ticket']['modified'])
            changed = call('POST', prefix + 'update_status', headers=headers, data=update)
            assert changed.status_code == 200, changed.status_code
            assert changed.json['message']['status'] == 'Resolved'
            repeated = call('POST', prefix + 'update_status', headers=headers, data=update)
            assert repeated.status_code == 200 and repeated.json['message'] == changed.json['message']
            passed('Status update and identical HTTP retry succeed without duplicate operation')
            for name in [foreign_ticket['name'], 'unavailable-foreign-ticket']:
                foreign = call('GET', prefix + 'get_ticket', query_string={'name': name})
                assert foreign.status_code == 403, foreign.status_code
            passed('Existing other-customer Issue and nonexistent Issue denied over authenticated HTTP')
            old_cookie = client.get_cookie('sid', domain='audit.localhost')
            assert old_cookie is not None
            logout = call('POST', '/api/method/logout', headers=headers)
            assert logout.status_code == 200, logout.status_code
            after_logout = call('GET', prefix + 'list_tickets')
            assert after_logout.status_code in {401, 403}, after_logout.status_code
            replay = Client(frappe_app.application, Response)
            replay.set_cookie('sid', old_cookie.value, domain='audit.localhost')
            replayed = replay.get(prefix + 'list_tickets', base_url=base, buffered=True)
            assert replayed.status_code in {401, 403}, replayed.status_code
            replayed.close()
            passed('Native logout invalidates access and replay of the old session cookie')
            relogin = call('POST', '/api/method/login', data={'usr': tech.name, 'pwd': password})
            password = None
            assert relogin.status_code == 200, relogin.status_code
            # Disable only the synthetic user; a previously issued cookie must stop working.
            connect()
            frappe.db.set_value('User', tech.name, 'enabled', 0)
            frappe.db.commit()
            frappe.clear_cache(user=tech.name)
            frappe.destroy()
            disabled = call('GET', prefix + 'list_tickets')
            assert disabled.status_code in {401, 403}, disabled.status_code
            passed('Disabled synthetic user cannot retain access with an existing session cookie')
        print(f'TOTAL: {count} real Frappe HTTP scenarios passed; production not accessed.')
    finally:
        frappe.destroy()
        frappe_app._site, frappe_app._sites_path = old_app_site, old_sites_path
        if fixtures:
            connect()
            # Remove receipts/notifications before linked Issues, then fixture users/roles.
            for dt, filters in [(api.EVENT, {'issue': ['in', fixture_issues]}),
                    ('SS97 Client Notification', {'for_user': ['in', TestTicketBridge.users]}),
                    ('ToDo', {'allocated_to': ['in', TestTicketBridge.users]})]:
                for name in frappe.get_all(dt, filters=filters, pluck='name'):
                    frappe.delete_doc(dt, name)
            for name in fixture_issues:
                if frappe.db.exists('Issue', name):
                    frappe.delete_doc('Issue', name)
            frappe.db.commit()
            TestTicketBridge.tearDownClass()
            frappe.destroy()


if __name__ == '__main__':
    main()
