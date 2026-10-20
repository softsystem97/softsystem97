"""Isolated source-contract tests; no remote client, database or production access.

The API facade is synthetic. These tests do not validate deployed Server Scripts,
native Frappe permissions, Stripe confirmation or the missing technician controller.
"""
import html
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
NATIVE_RUNTIME = '--frappe-site' in sys.argv


def load(relative):
    spec = importlib.util.spec_from_file_location(Path(relative).stem, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


api = load('integrations/ss97_client_support/client_ticket_api.py')
types = load('integrations/ss97_client_ops/ticket_types.py')
workspace = load('integrations/ss97_client_support/ticket_workspace.py')


def js_function(script, name):
    start = script.index('  function ' + name + '(')
    opening = script.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (script[end] == '{') - (script[end] == '}')
        end += 1
    return script[start:end]


class Denied(Exception):
    pass


class HistoricalSourceTests(unittest.TestCase):
    @unittest.skipUnless(NATIVE_RUNTIME, 'Requires initialized isolated Frappe runtime')
    def test_native_write_gate_rejects_get_guest_and_disabled_user(self):
        import frappe
        from softsystem97.integrations.historical_ticket_guard import require_write_session

        for method, user, enabled in [('GET', 'a@example.invalid', True),
                ('POST', 'Guest', True), ('POST', 'a@example.invalid', False)]:
            with self.subTest(method=method, user=user, enabled=enabled), \
                    patch.object(frappe.local, 'request', SimpleNamespace(method=method), create=True), \
                    patch.object(frappe.local, 'session', frappe._dict(user=user), create=True), \
                    patch.object(frappe.db, 'get_value', return_value=enabled):
                with self.assertRaises(frappe.PermissionError):
                    require_write_session()

    @unittest.skipUnless(NATIVE_RUNTIME, 'Requires initialized isolated Frappe runtime')
    def test_native_write_gate_accepts_only_active_post_and_grants_nothing(self):
        import frappe
        from softsystem97.integrations.historical_ticket_guard import require_write_session

        with patch.object(frappe.local, 'request', SimpleNamespace(method='POST'), create=True), \
                patch.object(frappe.local, 'session', frappe._dict(user='a@example.invalid'), create=True), \
                patch.object(frappe.db, 'get_value', return_value=True), \
                patch.object(frappe.db, 'set_value') as write:
            self.assertTrue(require_write_session())
            write.assert_not_called()

    def facade(self, user='client@example.invalid', enabled=True, **args):
        row = {'name': 'FAKE-1', 'raised_by': 'client@example.invalid',
               'ss97_contact_email': '', 'subject': 'Synthetic'}
        inserted = Mock(name='insert')
        inserted.name = 'COMMENT-FAKE'
        doc = Mock()
        doc.as_dict.return_value = row
        doc.insert.return_value = inserted

        def value(doctype, name, *unused, **kwargs):
            return enabled if doctype == 'User' else row if name == 'FAKE-1' else None

        def throw(message, exception=Denied):
            raise exception(message)

        f = SimpleNamespace(session=SimpleNamespace(user=user),
            db=SimpleNamespace(get_value=value, commit=Mock()),
            form_dict={'action': 'get', 'name': 'FAKE-1', **args}, response={},
            get_doc=Mock(return_value=doc), get_all=Mock(return_value=[]),
            get_list=Mock(return_value=[]), throw=throw,
            call=Mock(return_value=True),
            AuthenticationError=Denied, PermissionError=Denied,
            utils=SimpleNamespace(escape_html=html.escape,
                strip_html=lambda text: re.sub('<[^>]+>', '', text)))
        return f

    def execute(self, f):
        namespace = {'frappe': f}
        exec(compile(api.SERVER_SCRIPT, 'historical-client-api', 'exec'), namespace)
        return f.response.get('message')

    def test_owner_reads_allowed_fields(self):
        result = self.execute(self.facade())
        self.assertEqual(result['doc']['name'], 'FAKE-1')
        self.assertNotIn('password', result['doc'])

    def test_guest_and_disabled_accounts_rejected(self):
        for f in [self.facade(user='Guest'), self.facade(enabled=False)]:
            with self.subTest(user=f.session.user), self.assertRaises(Denied):
                self.execute(f)
            f.get_doc.assert_not_called()

    def test_foreign_and_missing_tickets_use_same_denial(self):
        messages = []
        for f in [self.facade(user='other@example.invalid'), self.facade(name='MISSING')]:
            with self.assertRaises(Denied) as error:
                self.execute(f)
            messages.append(str(error.exception))
            f.get_doc.assert_not_called()
        self.assertEqual(messages[0], messages[1])

    def test_private_and_unclassified_comments_never_returned(self):
        f = self.facade()
        contents = ['[Client] hello', '[Technicien→Client] reply',
                    '[Interne] confidential', '[Technicien→Administrateur] private',
                    '[Admin→Technicien] private', 'unclassified private note',
                    '[Client] [Interne] hidden', '<p>[Interne] hidden</p>']
        f.get_all.return_value = [dict(content=c, comment_type='Comment') for c in contents]
        result = self.execute(f)
        self.assertEqual([r['content'] for r in result['comments']], contents[:2])

    def test_file_permission_denial_does_not_fallback_to_unfiltered_files(self):
        f = self.facade()
        f.get_list.side_effect = Denied('native file permission')
        self.assertEqual(self.execute(f)['files'], [])
        self.assertEqual([c.args[0] for c in f.get_all.call_args_list], ['Comment'])

    def test_client_comment_escapes_markup_and_does_not_commit(self):
        f = self.facade(action='comment', content='<img src=x onerror=alert(1)>')
        self.assertTrue(self.execute(f)['ok'])
        payload = f.get_doc.call_args.args[0]
        self.assertNotIn('<img', payload['content'])
        self.assertIn('&lt;img', payload['content'])
        f.db.commit.assert_not_called()
        f.call.assert_called_once_with(
            'softsystem97.integrations.historical_ticket_guard.require_write_session')

    def test_write_gate_failure_prevents_comment_insert(self):
        f = self.facade(action='comment', content='Synthetic')
        f.call.side_effect = Denied('GET denied')
        with self.assertRaises(Denied):
            self.execute(f)
        f.get_doc.assert_not_called()

    def test_creation_remains_denied_without_secure_payment_flow(self):
        f = self.facade(action='create')
        with self.assertRaises(Denied):
            self.execute(f)
        f.get_doc.assert_not_called()

    def workflow(self):
        module = ModuleType('integrations.ss97_tickets.workflow_logic')
        module.next_ss97_ticket_ref = Mock(return_value='SYNTHETIC-REF')
        module.prepare_new_issue = Mock()
        return module

    def test_payment_preparation_failure_prevents_ticket_insert(self):
        workflow = self.workflow()
        workflow.prepare_new_issue.side_effect = Denied('payment not confirmed')
        client = Mock()
        with patch.dict(sys.modules, {'integrations.ss97_tickets.workflow_logic': workflow}):
            with self.assertRaises(Denied):
                types.create_typed_ticket(client, customer='Synthetic Customer')
        client.insert.assert_not_called()

    def test_successful_preparation_is_preserved_before_insert(self):
        workflow = self.workflow()
        workflow.prepare_new_issue.side_effect = lambda payload: payload.update(ss97_payment_status='synthetic')
        client = Mock()
        client.insert.return_value = {'name': 'SYNTHETIC-ISSUE'}
        with patch.dict(sys.modules, {'integrations.ss97_tickets.workflow_logic': workflow}):
            result = types.create_typed_ticket(client, customer='Synthetic Customer')
        self.assertTrue(result['ok'])
        self.assertEqual(client.insert.call_args.args[0]['ss97_payment_status'], 'synthetic')

    def test_uncertain_insert_is_not_retried_or_exception_disclosed(self):
        workflow = self.workflow()
        client = Mock()
        client.insert.side_effect = TimeoutError('private remote response')
        with patch.dict(sys.modules, {'integrations.ss97_tickets.workflow_logic': workflow}):
            result = types.create_typed_ticket(client, customer='Synthetic Customer')
        self.assertFalse(result['ok'])
        client.insert.assert_called_once()
        self.assertNotIn('private remote response', json.dumps(result))

    def test_workspace_payment_and_assignment_decisions_in_node(self):
        _, script = workspace.ticket_detail_body_and_js()
        functions = []
        for name in ['canAccess', 'stOf', 'isReallyPaid']:
            functions.append(js_function(script, name))
        program = '''const assert = require('node:assert/strict');
let assignedRoles=['SS97 Technician'];
const roles=()=>assignedRoles, sessionUser=()=> 'a@example.invalid';
const isStaff=()=>assignedRoles.includes('SS97 Technician');
const TOKEN_ACCESS=false, followToken='';
''' + '\n'.join(functions) + '''
assert.equal(canAccess({name:'FAKE',ss97_technician:'a@example.invalid'}),true);
assert.equal(canAccess({name:'FAKE',ss97_technician:'b@example.invalid'}),false);
assignedRoles=[];
assert.equal(canAccess({name:'FAKE',ss97_technician:'a@example.invalid'}),false);
for (const state of ['non confirmé','unconfirmed','pending','refunded','unpaid']) {
 assert.equal(isReallyPaid({ss97_payment_status:state,ss97_payment_ref:'checkout-ref'}),false);
}
assert.equal(isReallyPaid({ss97_payment_ref:'checkout-ref'}),false);
assert.equal(isReallyPaid({ss97_payment_status:'paid'}),true);
assert.equal(isReallyPaid({ss97_ticket_status:'Paiement confirmé'}),true);
assert.equal(isReallyPaid({ss97_ticket_status:'Paiement confirmé puis annulé'}),false);
'''
        result = subprocess.run(['node', '-e', program], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_client_page_calls_scoped_api_and_clears_data_after_denial(self):
        _, script = workspace.ticket_detail_body_and_js()
        program = '''const assert=require('node:assert/strict');
let name='FAKE', followToken='', DOC={name:'OLD'}, CLIENT_DETAIL=null, TOKEN_ACCESS=false;
let user='client@example.invalid', rendered=null;
const elements={};
const document={getElementById:(id)=>(elements[id]??={innerHTML:'old private data',style:{}})};
const sessionUser=()=>user, isTechOrAdmin=()=>false;
const applyTicketDoc=(doc)=>{rendered=doc;DOC=doc;};
let request;
const frappe={call:(options)=>{request=options;}};
const window={frappe:frappe};
''' + js_function(script, 'clearTicket') + js_function(script, 'loadDoc') + '''
loadDoc();
assert.equal(request.method,'ss97_client_ticket_api');
assert.deepEqual(request.args,{action:'get',name:'FAKE'});
request.callback({message:{doc:{name:'FAKE'},comments:[]}});
assert.equal(rendered.name,'FAKE');
request.error();
assert.equal(DOC,null);
assert.equal(CLIENT_DETAIL,null);
assert.equal(elements['tk-msgs'].innerHTML,'');
DOC={name:'OLD'};
user='Guest';
loadDoc();
assert.equal(DOC,null);
assert.equal(elements['tk-hist'].innerHTML,'');
'''
        result = subprocess.run(['node', '-e', program], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    if '--frappe-site' in sys.argv:
        import os
        import frappe

        index = sys.argv.index('--frappe-site')
        site = sys.argv[index + 1]
        del sys.argv[index:index + 2]
        if not site.startswith(('audit.', 'test_')):
            raise SystemExit('Disposable site required')
        sites = Path.cwd() / 'sites'
        os.chdir(sites)
        frappe.init(site=site, sites_path=str(sites))
        frappe.connect()
        if not frappe.conf.allow_tests:
            raise SystemExit('allow_tests required')
        from frappe.utils.safe_exec import safe_exec

        def restricted_execute(self, facade):
            safe_exec(api.SERVER_SCRIPT, _globals={'frappe': facade})
            return facade.response.get('message')

        HistoricalSourceTests.execute = restricted_execute
        try:
            # Enable only the compiler call in this process; no site config write.
            with patch('frappe.utils.safe_exec.is_safe_exec_enabled', return_value=True):
                program = unittest.main(verbosity=2, exit=False)
        finally:
            frappe.db.rollback()
            frappe.destroy()
        raise SystemExit(0 if program.result.wasSuccessful() else 1)
    else:
        unittest.main(verbosity=2)
