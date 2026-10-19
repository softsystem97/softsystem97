"""Fail-closed policy for the replacement bridge, not the unknown legacy portal."""
import frappe

FORBIDDEN_ROLES = {'system manager', 'administrator', 'all', 'guest', 'customer', 'candidat ss97'}
TRANSITIONS = {
    'Open': ['Replied', 'On Hold', 'Resolved'],
    'Replied': ['On Hold', 'Resolved'],
    'On Hold': ['Replied', 'Resolved'],
    'Resolved': ['Closed'],
    'Closed': [],
}


def settings():
    config = frappe.conf.get('ss97_ticket_bridge')
    if not isinstance(config, dict) or config.get('enabled') is not True:
        frappe.throw('Pont de développement désactivé.', frappe.PermissionError)
    if config.get('compatibility_confirmed') is not True:
        frappe.throw('Compatibilité non validée.', frappe.PermissionError)
    role = config.get('technician_role')
    if not isinstance(role, str) or not role.strip() or role.casefold() in FORBIDDEN_ROLES:
        frappe.throw('Rôle technicien non validé.', frappe.PermissionError)
    if not frappe.db.exists('Role', {'name': role, 'disabled': 0}):
        frappe.throw('Rôle technicien indisponible.', frappe.PermissionError)
    if config.get('profile_required') is not False:
        frappe.throw('Le modèle de profil doit être validé : adaptateur requis ou absence confirmée.',
                     frappe.PermissionError)
    meta = frappe.get_meta('Issue')
    if (not all(meta.has_field(field) for field in ['subject', 'description', 'raised_by', 'customer', 'status'])
            or meta.get_field('customer').options != 'Customer'
            or meta.get_field('status').fieldtype != 'Select'
            or set(meta.get_field('status').options.splitlines()) != set(TRANSITIONS)):
        frappe.throw('Modèle Issue incompatible.', frappe.PermissionError)
    if frappe.db.exists('Workflow', {'document_type': 'Issue', 'is_active': 1}):
        frappe.throw('Workflow Issue actif : adaptateur requis.', frappe.PermissionError)
    if frappe.db.exists('Server Script', {'script_type': 'DocType Event',
            'reference_doctype': 'Issue', 'disabled': 0}):
        frappe.throw('Scripts Issue actifs : compatibilité et adaptateur requis.', frappe.PermissionError)
    if config.get('email_enabled') is True and frappe.db.exists('Notification', {
            'document_type': 'Issue', 'enabled': 1, 'channel': 'Email'}):
        frappe.throw('Producteur e-mail Issue déjà actif : doublons à résoudre.', frappe.PermissionError)
    return config


def active_user(user=None):
    user = user or frappe.session.user
    if not user or user == 'Guest' or not frappe.db.get_value('User', user, 'enabled'):
        frappe.throw('Connexion active requise.', frappe.PermissionError)
    return user


def technician(user=None):
    config = settings()
    user = active_user(user)
    if config['technician_role'] not in frappe.get_roles(user):
        frappe.throw('Accès technicien refusé.', frappe.PermissionError)
    return user


def customer():
    settings()
    user = active_user()
    if 'Customer' not in frappe.get_roles(user):
        frappe.throw('Accès client refusé.', frappe.PermissionError)
    # Deliberately no fuzzy email/contact fallback or caller-selected Customer.
    links = set(frappe.get_all('Portal User', filters={
        'user': user, 'parenttype': 'Customer', 'parentfield': 'portal_users'}, pluck='parent'))
    if len(links) != 1:
        frappe.throw('Un lien Portal User vers un client unique est requis.', frappe.PermissionError)
    name = links.pop()
    if not frappe.db.exists('Customer', {'name': name, 'disabled': 0}):
        frappe.throw('Client actif requis.', frappe.PermissionError)
    return user, name


def actor(audience):
    if audience == 'technician':
        return technician()
    if audience == 'client':
        return customer()[0]
    frappe.throw('Espace invalide.', frappe.PermissionError)


def assigned(name, user):
    return bool(frappe.db.exists('ToDo', {'reference_type': 'Issue', 'reference_name': name,
                                        'allocated_to': user, 'status': 'Open'}))


def authorize(doc, audience):
    settings()
    if audience == 'technician':
        user = technician()
        allowed = assigned(doc.name, user)
    elif audience == 'client':
        user, client = customer()
        allowed = doc.raised_by == user and doc.customer == client
    else:
        frappe.throw('Espace invalide.', frappe.PermissionError)
    if not allowed:
        frappe.throw('Ticket inaccessible.', frappe.PermissionError)
    return user


def dispatcher():
    settings()
    active_user()
    frappe.only_for('System Manager')
