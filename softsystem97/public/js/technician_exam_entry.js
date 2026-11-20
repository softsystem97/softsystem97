/* Repairs two legacy navigation defects without changing exam outcomes.
 * The server, never the browser, selects the signed-in user's own invitation.
 */
(function () {
  'use strict';
  if (!/^\/(?:technicien|espace-technicien)(?:\/|$)/.test(location.pathname)) return;
  if (window.__ss97ExamEntryBridge) return;
  window.__ss97ExamEntryBridge = true;

  var prefix = '/api/method/softsystem97.portal.technician_exam_entry.';
  var legacyRoles = 'frappe.core.doctype.user.user.get_roles';

  function installLegacyRolesFix() {
    if (!window.frappe || typeof frappe.call !== 'function') return false;
    if (frappe.call.__ss97ExamRolesFixed) return true;
    var original = frappe.call;
    function repaired(options) {
      // The old method does not exist in Frappe v16.  The replacement only
      // returns roles for this authenticated session, never a supplied uid.
      if (options && typeof options === 'object' && options.method === legacyRoles) {
        var safeOptions = Object.assign({}, options, {
          method: prefix + 'get_my_portal_roles', args: {}
        });
        return original.call(this, safeOptions);
      }
      return original.apply(this, arguments);
    }
    Object.assign(repaired, original);
    repaired.__ss97ExamRolesFixed = true;
    frappe.call = repaired;
    return true;
  }

  function addExamLinks() {
    Array.prototype.forEach.call(document.querySelectorAll('a[href]'), function (link) {
      var href;
      try { href = new URL(link.getAttribute('href'), location.href); } catch (ignored) { return; }
      if (href.origin !== location.origin || href.pathname !== '/examen-technicien'
          || href.search || link.dataset.ss97ExamEntryBound) return;
      link.dataset.ss97ExamEntryBound = '1';
      link.addEventListener('click', function (event) {
        event.preventDefault();
        event.stopImmediatePropagation();
        if (link.dataset.ss97ExamEntryLoading) return;
        link.dataset.ss97ExamEntryLoading = '1';
        fetch(prefix + 'get_my_exam_entry', {
          credentials: 'same-origin', headers: {'Accept': 'application/json'}
        }).then(function (response) {
          if (!response.ok) throw Error('Dossier d’examen indisponible.');
          return response.json();
        }).then(function (body) {
          var relative = body && body.message && body.message.url;
          if (typeof relative !== 'string') throw Error('Invitation absente.');
          var destination = new URL(relative, location.origin);
          if (destination.origin !== location.origin ||
              destination.pathname !== '/examen-technicien' ||
              !destination.searchParams.get('app') ||
              !destination.searchParams.get('token')) throw Error('Invitation invalide.');
          location.assign(destination.href); // This opens the gate; it does not start an attempt.
        }).catch(function () {
          var note = document.getElementById('ss97-exam-entry-error');
          if (!note) {
            note = document.createElement('p');
            note.id = 'ss97-exam-entry-error';
            note.setAttribute('role', 'alert');
            link.insertAdjacentElement('afterend', note);
          }
          note.textContent = 'Votre examen personnel est indisponible. Vérifiez le dossier de candidature avec SS97.';
        }).finally(function () { delete link.dataset.ss97ExamEntryLoading; });
      }, true);
    });
  }

  function boot() {
    installLegacyRolesFix();
    addExamLinks();
    // Some older portal pages construct their sidebar after DOMContentLoaded.
    window.addEventListener('ss97:tech-ready', addExamLinks);
  }
  // frappe-web.bundle is already loaded by the time web_include_js executes.
  // Repair the legacy call before older frappe.ready callbacks can fire.
  installLegacyRolesFix();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, {once: true});
  } else boot();
})();
