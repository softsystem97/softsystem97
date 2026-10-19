"""Real Chromium UI tests with intercepted HTTP fixtures, never production.

Requires playwright==1.58.0 and a locally installed Chromium. This does not
validate a live Frappe session, SSO/2FA, or the historical production portal.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / 'softsystem97/www/ss97-dev-technician.html').read_text()
JS = (ROOT / 'softsystem97/public/js/ticket_bridge.js').read_text()


def html(guest):
    content = TEMPLATE.split('{% block page_content %}', 1)[1].split('{% endblock %}', 1)[0]
    before, rest = content.split('{% if is_guest %}', 1)
    login, rest = rest.split('{% else %}', 1)
    workspace, after = rest.split('{% endif %}', 1)
    return '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + \
        '<script>window.frappe={csrf_token:""}</script>' + before + (login if guest else workspace) + after


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium', default='/usr/bin/chromium')
    parser.add_argument('--screenshot')
    args = parser.parse_args()
    count = 0
    def passed(label):
        nonlocal count
        count += 1
        print('PASS ' + label, flush=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=args.chromium, headless=True)
        context = browser.new_context(viewport={'width': 1200, 'height': 900})
        page = context.new_page()
        page.set_default_timeout(10000)
        state = {'guest': True, 'deny': False, 'conflict': False, 'failed_comment': False,
                 'status': 'Open', 'modified': 'revision-1', 'login_success': None}
        requests = []
        ticket = {'name': 'ISS-LAB-1', 'subject': 'Controlled support request', 'description': 'Synthetic',
                  'status': 'Open', 'modified': 'revision-1', 'allowed_statuses': ['Resolved']}
        def handle(route):
            request = route.request
            path = urlparse(request.url).path
            if path == '/ss97-dev-technician':
                return route.fulfill(status=200, content_type='text/html', body=html(state['guest']))
            if path.endswith('ticket_bridge.js'):
                return route.fulfill(status=200, content_type='text/javascript', body=JS)
            if not path.startswith('/api/method/'):
                return route.abort()
            payload = parse_qs(request.post_data or urlparse(request.url).query)
            requests.append((path, request.method, payload, request.url))
            if path.endswith('/login'):
                if state['login_success']:
                    state['guest'] = False
                    return route.fulfill(status=200, content_type='application/json',
                        body=json.dumps({'message': state['login_success']}))
                return route.fulfill(status=401, content_type='application/json', body='{}')
            if state['deny']:
                return route.fulfill(status=403, content_type='application/json', body='{}')
            method = path.rsplit('.', 1)[-1]
            if method == 'update_status' and state['conflict']:
                return route.fulfill(status=409, content_type='application/json', body='{}')
            if method == 'add_intervention' and not state['failed_comment']:
                state['failed_comment'] = True
                return route.abort('failed')
            if method == 'list_tickets':
                result = {'tickets': [ticket], 'page_size': 50}
            elif method == 'get_ticket':
                result = {'ticket': {**ticket, 'status': state['status'], 'modified': state['modified'],
                    'allowed_statuses': [] if state['status'] == 'Closed' else ['Resolved']},
                    'history': [{'creation': 'Lab', 'detail': '<img src=x onerror=alert(1)> shared text'}]}
            elif method == 'get_notifications':
                result = {'notifications': [{'title': 'Lab update', 'message': 'Synthetic notification'}]}
            else:
                result = {'name': ticket['name']}
            return route.fulfill(status=200, content_type='application/json', body=json.dumps({'message': result}))
        page.route('https://ss97.test/**', handle)
        page.goto('https://ss97.test/ss97-dev-technician')
        assert page.locator('#ss97-password').get_attribute('type') == 'password'
        page.get_by_role('button', name='Afficher le mot de passe', exact=True).click()
        assert page.locator('#ss97-password').get_attribute('type') == 'text'
        assert page.locator('#ss97-show-password').get_attribute('aria-pressed') == 'true'
        page.evaluate('window.dispatchEvent(new Event("blur"))')
        assert page.locator('#ss97-password').get_attribute('type') == 'password'
        passed('Password hidden by default, accessible toggle, remasked on blur')
        page.locator('#ss97-email').fill('browser-lab@example.invalid')
        page.locator('#ss97-password').fill('synthetic UI input')
        page.get_by_role('button', name='Se connecter', exact=True).click()
        page.get_by_role('alert').filter(has_text='Session expirée').wait_for()
        login = requests[-1]
        assert login[1] == 'POST' and 'pwd' in login[2] and '?' not in login[3]
        assert page.locator('#ss97-password').input_value() == ''
        passed('Login uses POST with no password in URL and clears the field on failure')
        for success in ['No App', 'Logged In']:
            state.update(guest=True, login_success=success)
            page.goto('https://ss97.test/ss97-dev-technician')
            page.locator('#ss97-email').fill('browser-lab@example.invalid')
            page.locator('#ss97-password').fill('synthetic UI input')
            page.get_by_role('button', name='Se connecter', exact=True).click()
            page.locator('#ss97-workspace').wait_for()
            assert page.url == 'https://ss97.test/ss97-dev-technician'
            passed('Successful native login response redirects: ' + success)
        state['login_success'] = None
        state['guest'] = False
        page.reload()
        page.locator('#ss97-tickets button').wait_for()
        page.locator('#ss97-tickets button').click()
        page.locator('#ss97-detail:visible').wait_for()
        assert 'ISS-LAB-1' in page.locator('#ss97-title').inner_text()
        passed('Technician dashboard opens assigned ticket detail')
        assert page.locator('#ss97-history img').count() == 0
        assert '<img' in page.locator('#ss97-history').inner_text()
        passed('History is rendered as text, without executing markup')
        state['conflict'] = True
        page.locator('#ss97-status-form button').click()
        page.get_by_role('alert').filter(has_text='Le ticket a changé').wait_for()
        assert requests[-1][1] == 'POST' and requests[-1][2]['expected_modified'] == ['revision-1']
        passed('Conflicting status update displays refresh guidance and sends expected version')
        state['conflict'] = False
        page.locator('#ss97-content').fill('Shared intervention')
        page.locator('#ss97-comment button').click()
        page.wait_for_function('!document.querySelector("#ss97-comment button").disabled')
        page.reload()
        page.locator('#ss97-tickets button').wait_for()
        page.locator('#ss97-tickets button').click()
        page.locator('#ss97-detail:visible').wait_for()
        page.locator('#ss97-content').fill('Shared intervention')
        page.locator('#ss97-comment button').click()
        page.wait_for_function('!document.querySelector("#ss97-comment button").disabled')
        comments = [r for r in requests if r[0].endswith('.add_intervention')]
        assert len(comments) == 2 and comments[0][2]['request_id'] == comments[1][2]['request_id']
        passed('Network retry after page reload retains the same idempotency key')
        state['deny'] = True
        page.locator('#ss97-refresh').click()
        page.get_by_role('alert').filter(has_text='Accès refusé').wait_for()
        assert not page.locator('#ss97-detail').is_visible()
        assert page.locator('#ss97-tickets').inner_text() == ''
        passed('Forbidden response clears ticket data and displays access error')
        state['deny'] = False
        page.locator('#ss97-audience').select_option('client')
        page.locator('#ss97-create:visible').wait_for()
        page.locator('#ss97-subject').fill('Synthetic client ticket')
        page.locator('#ss97-description').fill('Controlled input')
        page.locator('#ss97-create button').click()
        page.wait_for_function('!document.querySelector("#ss97-create button").disabled')
        create = next(r for r in requests if r[0].endswith('.create_ticket'))
        assert create[1] == 'POST' and 'customer' not in create[2] and 'raised_by' not in create[2]
        passed('Client creation does not send a caller-selected customer or identity')
        state['status'] = 'Closed'
        page.locator('#ss97-tickets button').click()
        page.locator('#ss97-detail:visible').wait_for()
        assert not page.locator('#ss97-status-form').is_visible()
        assert not page.locator('#ss97-comment').is_visible()
        passed('Closed ticket detail disables status and comment forms')
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        if args.screenshot:
            page.screenshot(path=args.screenshot, full_page=True)
        passed('Mobile viewport has no horizontal overflow')
        browser.close()
    print(f'TOTAL: {count} browser scenarios passed (HTTP fixtures; not live authentication).')


if __name__ == '__main__':
    main()
