"""Private metadata inventory. Never execute/export route source or conditions."""
from pathlib import Path
import hashlib
import re
import frappe

ROUTES = ('espace-technicien', 'espace-technicien/tickets')


def _file_manifest(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return None
    if path.stat().st_size > 2_000_000:
        return {'path': str(path.relative_to(root)), 'inspection': 'size_limit'}
    return {'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def _symbols(value):
    if isinstance(value, dict):
        return {k: _symbols(v) for k, v in value.items()}
    if isinstance(value, str):
        return value if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*', value) else None
    return [_symbols(v) for v in (value or []) if _symbols(v) is not None]


def collect():
    """Administrative console only; not whitelisted and no writes or rendering."""
    frappe.only_for('System Manager')
    data = {'format': 'ss97-route-metadata-v1', 'executed_route': False,
            'source_exported': False, 'routes': list(ROUTES), 'apps': [], 'hooks': {}, 'workflows': []}
    for app in frappe.get_installed_apps():
        root = Path(frappe.get_app_path(app))
        candidates = []
        for route in ROUTES:
            for stem in (route, route.replace('-', '_')):
                for suffix in ('.py', '.html', '.md', '/index.py', '/index.html'):
                    item = _file_manifest(root, root / 'www' / (stem + suffix))
                    if item and item not in candidates:
                        candidates.append(item)
        data['apps'].append({'app': app, 'route_file_candidates': candidates})
    for hook in ('website_path_resolver', 'page_renderer', 'permission_query_conditions',
                 'has_permission', 'doc_events'):
        value = frappe.get_hooks(hook)
        if isinstance(value, dict):
            value = {key: val for key, val in value.items() if key in ('Issue', '*')}
        data['hooks'][hook] = _symbols(value)
    # Do not export arbitrary rewrite targets (possibly signed URLs).
    data['rewrite_rule_count'] = len(frappe.get_hooks('website_route_rules') or [])
    data['web_pages'] = frappe.get_all('Web Page', filters={'route': ['in', list(ROUTES)]},
                                     fields=['name', 'route', 'published', 'content_type'])
    meta = frappe.get_meta('Issue')
    data['issue_fields'] = {name: ({key: field.get(key) for key in
        ('fieldtype', 'options', 'permlevel', 'read_only', 'reqd')} if
        (field := meta.get_field(name)) else None) for name in ('ss97_technician', 'status', 'customer')}
    fields = ['role', 'permlevel', 'read', 'write', 'create', 'delete', 'submit', 'cancel', 'if_owner']
    data['issue_permissions'] = [{key: row.get(key) for key in fields} for row in meta.permissions]
    data['custom_permissions'] = frappe.get_all('Custom DocPerm', filters={'parent': 'Issue'}, fields=fields)
    data['technician_roles'] = frappe.get_all('Role', filters={'name': ['in',
        ['SS97 Technician', 'SS97 Technicien']]}, fields=['name', 'disabled', 'desk_access'])
    for name in frappe.get_all('Workflow', filters={'document_type': 'Issue'}, pluck='name'):
        doc = frappe.get_doc('Workflow', name)
        data['workflows'].append({'name': name, 'active': doc.is_active,
            'state_field': doc.workflow_state_field,
            'states': [{key: row.get(key) for key in ('state', 'doc_status', 'allow_edit')} for row in doc.states],
            'transitions': [{**{key: row.get(key) for key in ('state', 'action', 'next_state', 'allowed')},
                             'has_private_condition': bool(row.get('condition'))} for row in doc.transitions]})
    data['issue_server_scripts'] = frappe.get_all('Server Script', filters={'reference_doctype': 'Issue'},
        fields=['name', 'script_type', 'disabled', 'doctype_event'])
    data['limits'] = ['Route precedence not executed; inspect matching hooks privately',
        'No source/templates/conditions/config/customer records exported',
        'No account, assignment, payment or session validated']
    return data
