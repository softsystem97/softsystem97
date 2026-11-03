"""Tests of recovered builders/assets; no site installation, SDK or account writes."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from integrations.ss97_notifications import center
from integrations.ss97_technician_etape6 import deploy
from integrations.ss97_website.mission5_recruit import THEME


class TestLastDependencies(unittest.TestCase):
    def test_real_page_builder_uses_recovered_contract(self):
        guard = ModuleType('integrations.ss97_technician_operations.technician_guard')
        shell = ModuleType('integrations.ss97_technician_operations.workspace_shell')
        guard.technician_login_required_html = Mock(return_value='<p>LOGIN</p>')
        shell.open_shell = Mock(return_value='<main>')
        shell.close_shell = Mock(return_value='</main>')
        p = SimpleNamespace(TECH_CSS='<style>/* fixture */</style>',
                            TECH_DASH_JS='<script>/* fixture */</script>',
                            _presence_bar=lambda: 'PRESENCE', _kpi_block=lambda: 'KPI',
                            _ticket_tables=lambda: 'TICKETS')
        with patch.dict(sys.modules, {guard.__name__: guard, shell.__name__: shell}):
            html = deploy.page_tickets(p)
        shell.open_shell.assert_called_once_with('tickets')
        for expected in ('Mes tickets', 'data-tech-private', 'LOGIN', 'PRESENCE', 'KPI', 'TICKETS'):
            self.assertIn(expected, html)

    def test_builder_import_has_no_deployment_helpers_or_sdk(self):
        self.assertFalse(hasattr(deploy, 'main'))
        self.assertFalse(hasattr(deploy, 'deploy'))
        self.assertIn('<style>', THEME)

    def test_notification_external_and_ambiguous_paths_denied(self):
        for route in ('//evil.invalid/a', 'https://app.softsystem97.com.evil.invalid/a',
                      'https://app.softsystem97.com@evil.invalid/a',
                      'http://app.softsystem97.com/espace-technicien/tickets',
                      '/espace-technicien/tickets/../../app',
                      '/espace-technicien/tickets/%2e%2e/app',
                      '/espace-technicien/tickets%252f..%252fapp',
                      '/espace-technicien/tickets\\evil',
                      '/espace-technicien/tickets?x=" onmouseover="evil',
                      '/espace-client/tickets'):
            with self.subTest(route=route):
                self.assertEqual(center.sanitize_tech_route(route), '/espace-technicien/dashboard')

    def test_notification_known_local_and_absolute_routes(self):
        route = '/espace-technicien/tickets?ticket=SYNTHETIC-1'
        self.assertEqual(center.sanitize_tech_route(route), route)
        self.assertEqual(center.sanitize_tech_route('https://app.softsystem97.com' + route), route)

    def test_event_ticket_identifiers_are_encoded(self):
        self.assertEqual(center.tech_route_for_event('assigned', 'SYNTH&admin=1'),
                         '/espace-technicien/intervention?ticket=SYNTH%26admin%3D1')
        self.assertEqual(center.tech_route_for_event('closed', 'SYNTH-1'),
                         '/espace-technicien/historique?ticket=SYNTH-1')
        self.assertIn('&section=securite', center.tech_route_for_event('security', 'SYNTH-1'))

    def test_notification_assets_use_only_scoped_read_endpoint(self):
        source = center.notif_assets()
        self.assertIn('ticket_bridge.api.get_notifications', source)
        self.assertIn("credentials:'same-origin'", source)
        self.assertIn('textContent', source)
        self.assertNotIn('innerHTML', source)
        self.assertNotIn('frappe.client', source)
        self.assertNotIn("method:'POST'", source)
        self.assertNotIn('localStorage', source)
        self.assertIn('list.replaceChildren()', source)

    def test_notification_browser_flow_success_then_expired_session(self):
        script = center.NOTIF_BELL_JS.removeprefix('\n<script>').removesuffix('</script>\n')
        harness = r"""
const vm=require('node:vm');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.listeners={};this.textContent='';}
  appendChild(child){this.children.push(child);return child;}
  setAttribute(){}
  addEventListener(name,fn){this.listeners[name]=fn;}
  replaceChildren(){this.children=[];this.textContent='';}
}
const host=new Element('div');const calls=[];let allowed=true,envelope=false,denials=0;
const context={window:{ss97ScopedAccessDenied:()=>{denials++;}},document:{createElement:t=>new Element(t),querySelector:()=>host},
 fetch:async (url,options)=>{calls.push({url,options});return {ok:allowed||envelope,status:allowed||envelope?200:403,
 json:async()=>envelope?({exc_type:'PermissionError',exc:'denied'}):({message:{notifications:[{title:'<img src=x onerror=evil()>',reference_name:'SYNTH&x=1'}]}})};}};
vm.runInNewContext(SOURCE,context);
(async()=>{
 const root=host.children[0],button=root.children[0],list=root.children[1];
 if(calls.length)throw Error('unexpected automatic request');
 await button.listeners.click();
 const first={title:list.children[0].children[0].textContent,href:list.children[0].children[0].href};
 allowed=false;await button.listeners.click();
 envelope=true;await button.listeners.click();
 console.log(JSON.stringify({first,calls,denials,remaining:list.children.length,error:list.textContent,disabled:button.disabled}));
})().catch(e=>{console.error(e);process.exitCode=1;});
""".replace('SOURCE', json.dumps(script))
        result = subprocess.run(['node', '-e', harness], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        self.assertEqual(data['first']['title'], '<img src=x onerror=evil()>')
        self.assertEqual(data['first']['href'], '/espace-technicien/intervention?ticket=SYNTH%26x%3D1')
        self.assertEqual(data['remaining'], 0)
        self.assertFalse(data['disabled'])
        self.assertIn('indisponibles', data['error'])
        self.assertEqual(len(data['calls']), 3)
        self.assertEqual(data['denials'], 2)
        self.assertTrue(all(c['options']['credentials'] == 'same-origin' for c in data['calls']))

    def test_legacy_writing_notification_producers_not_imported(self):
        self.assertFalse(hasattr(center, 'push_notification'))
        self.assertFalse(hasattr(center, 'notify_ticket_event'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
