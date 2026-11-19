"""Offline regression checks for technician page controls and scroll affordance."""

from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'softsystem97/public/js/technician_portal_ui.js'
CSS = ROOT / 'softsystem97/public/css/technician_scroll.css'
HOOKS = ROOT / 'softsystem97/hooks.py'


class PortalUiContracts(unittest.TestCase):
    def test_valid_javascript_with_legacy_message_functions_restored(self):
        subprocess.run(['node', '--check', str(SCRIPT)], check=True, capture_output=True)
        code = SCRIPT.read_text(encoding='utf-8')
        self.assertIn('window.ss97OpenTicket = function', code)
        self.assertIn('window.ss97LoadMessages = function', code)
        self.assertIn('location.reload()', code)
        self.assertIn("'/espace-technicien/intervention?ticket='", code)
        self.assertIn('safeTicket(ticket)', code)
        self.assertIn('navigator.clipboard.writeText(ticket)', code)
        self.assertIn('dashboard#ss97-tech-chat', code)
        self.assertIn("'/espace-technicien/notifications'", code)

    def test_skills_end_with_servers_and_printers_for_four_languages(self):
        code = SCRIPT.read_text(encoding='utf-8')
        for word in ('serveurs, imprimantes)', 'servers, printers)',
                     'servidores, impresoras)', 'sèvè, enprimant)'):
            self.assertIn(word, code)
        for extra in ('Odoo', 'ERPNext, TeamViewer', 'Google, Odoo'):
            self.assertNotIn(extra, code)

    def test_visible_scrollbar_and_controlled_arrows(self):
        code = SCRIPT.read_text(encoding='utf-8')
        css = CSS.read_text(encoding='utf-8')
        self.assertIn("'ss97-scroll-arrows'", code)
        self.assertIn('scrollMain(1)', code)
        self.assertIn('scrollMain(-1)', code)
        self.assertIn('overflow-y: scroll !important', css)
        self.assertIn('::-webkit-scrollbar', css)
        self.assertIn('technician_scroll.css?v=20261119-tech-scroll-1', HOOKS.read_text())
        self.assertIn('technician_portal_ui.js?v=20261119-portal-ui-3', HOOKS.read_text())

    def test_browser_patch_does_not_enable_remote_or_fake_profile_saves(self):
        code = SCRIPT.read_text(encoding='utf-8')
        self.assertIn("typeof window.ss97SaveProfile !== 'function'", code)
        self.assertIn('stopImmediatePropagation', code)
        self.assertNotIn('ignore_permissions', code)
        self.assertNotIn('meshcentral', code.lower())
        self.assertNotIn('window.ss97SaveProfile =', code)

    def test_messages_mutation_observer_does_not_rewrite_unchanged_text(self):
        code = SCRIPT.read_text(encoding='utf-8')
        self.assertIn("button.textContent !== t('copied') && button.textContent !== t('copy')", code)

    def test_buttons_have_capture_handlers_independent_of_inline_globals(self):
        code = SCRIPT.read_text(encoding='utf-8')
        self.assertIn('ss97RefreshBound', code)
        self.assertIn('ss97OpenBound', code)
        self.assertIn('event.stopImmediatePropagation()', code)


if __name__ == '__main__':
    unittest.main()
