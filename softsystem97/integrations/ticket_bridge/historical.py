"""Opt-in integration contract, not an implementation of the private workflow.

No route, payment callback, role grant or site configuration is installed here.
Only an administrator-reviewed server provider may decide business eligibility.
"""
from dataclasses import dataclass
import re

import frappe


@dataclass(frozen=True)
class AuthorizationRequest:
    issue: str
    revision: str
    operation: str
    actor: str
    customer: str
    technician: str
    status: str
    target_status: str


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    request: AuthorizationRequest
    policy_version: str


def enabled():
    config = frappe.conf.get('ss97_ticket_bridge') or {}
    return config.get('historical_integration') is True


def resolve_provider(method):
    # Method comes only from private site configuration, never HTTP parameters.
    return frappe.get_attr(method)


def validate_configuration(config, meta):
    value = config.get('historical_integration')
    if value is not None and type(value) is not bool:
        frappe.throw('Activation historique booléenne requise.', frappe.PermissionError)
    if value is not True:
        return
    field = meta.get_field('ss97_technician')
    if (config.get('technician_role') != 'SS97 Technician' or not field
            or field.fieldtype != 'Link' or field.options != 'User'):
        frappe.throw('Rôle canonique et lien ss97_technician vers User requis ; adaptateur de profil sinon.',
                     frappe.PermissionError)
    method = config.get('business_authorizer')
    if not isinstance(method, str) or not method.startswith('softsystem97.integrations.'):
        frappe.throw('Adaptateur métier serveur non configuré.', frappe.PermissionError)
    try:
        provider = resolve_provider(method)
    except (ImportError, AttributeError):
        frappe.throw('Adaptateur métier serveur absent.', frappe.PermissionError)
    if not callable(provider):
        frappe.throw('Adaptateur métier serveur invalide.', frappe.PermissionError)


def require_authorization(operation, doc=None, *, customer='', technician='', target_status=''):
    if not enabled():
        return ''
    config = frappe.conf.ss97_ticket_bridge
    request = AuthorizationRequest(
        issue=doc.name if doc else '', revision=str(doc.modified) if doc else '',
        operation=operation, actor=frappe.session.user,
        customer=doc.customer if doc else customer, technician=technician,
        status=doc.status if doc else '', target_status=target_status)
    decision = resolve_provider(config['business_authorizer'])(request)
    if (not isinstance(decision, AuthorizationDecision) or decision.allowed is not True
            or decision.request != request or not isinstance(decision.policy_version, str)
            or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', decision.policy_version)):
        frappe.throw('Opération refusée par la politique métier.', frappe.PermissionError)
    return ' [policy:' + decision.policy_version + ']'
