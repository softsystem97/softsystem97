"""User-run, read-only REST check. No credentials are read from files or logged."""
import argparse
import getpass
import json
import sys
import urllib.error
import urllib.request
import warnings
from urllib.parse import urlsplit


def is_authenticated_payload(payload):
    if not isinstance(payload, dict):
        return False
    identity = payload.get('message')
    return (isinstance(identity, str) and bool(identity.strip())
            and identity == identity.strip() and identity != 'Guest')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True, help='Authorized HTTPS site, no URL credentials')
    args = parser.parse_args()
    parsed = urlsplit(args.base_url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
        parser.error('An HTTPS origin without userinfo, query or path is required')
    if not sys.stdin.isatty():
        parser.error('Use an interactive terminal with hidden input; do not pipe credentials')
    # Run only after explicit authorization to use credentials for this destination.
    # Input is hidden and retained only in this process; never print request/response bodies.
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            key = getpass.getpass('API Key (hidden): ')
            secret = getpass.getpass('API Secret (hidden): ')
        except (getpass.GetPassWarning, EOFError):
            print('Hidden input unavailable; authentication check cancelled.')
            return 1
    request = urllib.request.Request(args.base_url.rstrip('/') + '/api/method/frappe.auth.get_logged_user',
                                     headers={'Authorization': 'token ' + key + ':' + secret})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None  # Never forward credentials to a redirect destination.
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
            payload = json.load(response)
            ok = is_authenticated_payload(payload)
    except urllib.error.HTTPError as exc:
        print(f'Authentication check failed (HTTP {exc.code}); response body suppressed.')
        return 1
    except (urllib.error.URLError, ValueError):
        print('Authentication check failed; network/response details suppressed.')
        return 1
    finally:
        key = secret = ''
    print('Authenticated REST request succeeded.' if ok else 'No authenticated user confirmed.')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
