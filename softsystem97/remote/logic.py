"""Pure helpers shared by the Frappe API and offline security tests."""

import hashlib
import hmac
import re
import secrets
from datetime import timedelta

CODE_LENGTH = 9
# The invitation is usable within a one-hour assistance window. This is not
# permission to control a desktop for one hour: local consent is still needed.
ASSISTANCE_WINDOW_MINUTES = 60
PENDING = frozenset({"CREATED", "CLIENT_READY", "CLIENT_APPROVED"})
TERMINAL = frozenset({"DECLINED", "ENDED", "EXPIRED", "ERROR"})


def assistance_window_end(starts_at):
    """Compute the fixed V1.1 window without depending on a Frappe site."""
    return starts_at + timedelta(minutes=ASSISTANCE_WINDOW_MINUTES)


def normalize_code(code):
    if not isinstance(code, str) or not re.fullmatch(r"[0-9]{9}", code):
        raise ValueError("Le code doit contenir exactement neuf chiffres.")
    return code


def code_digest(code, secret):
    code = normalize_code(code)
    if not isinstance(secret, str) or len(secret) < 32:
        raise ValueError("Clé serveur requise.")
    return hmac.new(secret.encode("utf-8"), code.encode("ascii"), hashlib.sha256).hexdigest()


def new_code():
    """Never use Python's predictable random generator for join codes."""
    return f"{secrets.randbelow(900_000_000) + 100_000_000:09d}"


def can_transition(previous, new):
    return new in {
        "CREATED": {"CLIENT_READY", "ENDED", "EXPIRED"},
        "CLIENT_READY": {"CLIENT_APPROVED", "DECLINED", "ENDED", "EXPIRED"},
        # ACTIVE must be set only by a verified MeshCentral event in a future adapter.
        "CLIENT_APPROVED": {"ENDED", "EXPIRED"},
        "ACTIVE": {"ENDED", "ERROR"},
    }.get(previous, set())
