"""Console-only update of four payment functions in the EXISTING ticket Web Page."""
import frappe

BLOCKS = {
    'isReallyPaid': 'isValidated',
    'clientPayNow': 'maybeConfirmReturn',
    'maybeConfirmReturn': 'renderReport',
    'applyTicketDoc': 'loadDoc',
}


def _bounds(text, start, end):
    left = text.index('  function ' + start + '(')
    right = text.index('  function ' + end + '(', left)
    return left, right


def patch_existing_page(dry_run=True):
    """Preserve HTML/design and all other functions; refuse unfamiliar page shapes."""
    frappe.only_for('System Manager')
    if type(dry_run) is not bool:
        frappe.throw('dry_run must be a JSON boolean', frappe.ValidationError)
    from integrations.ss97_client_support.ticket_workspace import ticket_detail_body_and_js
    rows = frappe.get_all('Web Page', filters={'route':'espace-client/ticket'}, pluck='name', limit_page_length=2)
    if len(rows) != 1:
        frappe.throw('Une page ticket existante unique est requise.', frappe.ValidationError)
    page = frappe.get_doc('Web Page', rows[0])
    _, reference = ticket_detail_body_and_js()
    changes = {}
    for field in ('main_section', 'main_section_html', 'javascript'):
        current = page.get(field) or ''
        if not current or 'function clientPayNow(' not in current:
            continue
        updated = current
        try:
            for start, end in BLOCKS.items():
                left, right = _bounds(updated, start, end)
                source_left, source_right = _bounds(reference, start, end)
                updated = updated[:left] + reference[source_left:source_right] + updated[right:]
        except ValueError:
            frappe.throw('Script ticket différent : revue manuelle requise.', frappe.ValidationError)
        if updated != current:
            changes[field] = updated
    if not changes:
        return {'changed':False, 'dry_run':dry_run, 'reason':'Already applied or no compatible script found'}
    if not dry_run:
        page.update(changes)
        page.save()  # Native permission/version/validation hooks; no commit here.
    return {'changed':not dry_run, 'dry_run':dry_run, 'page':page.name, 'fields':list(changes),
        'functions':list(BLOCKS)}
