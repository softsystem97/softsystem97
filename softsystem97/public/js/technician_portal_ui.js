/* Visible, functional technician navigation for legacy Frappe Web Pages.
 * Remote desktop is deliberately NOT activated by a browser-only patch.
 */
(function () {
  'use strict';
  if (!/^\/espace-technicien(?:\/|$)/.test(location.pathname)) return;
  if (window.__ss97TechnicianPortalUiV1) return;
  window.__ss97TechnicianPortalUiV1 = true;

  var messages = {
    fr: {skills: 'Domaines (M365, Windows, macOS, Linux, réseaux, cybersécurité, cloud, sauvegarde, serveurs, imprimantes)',
      down: 'Descendre', up: 'Remonter', copy: 'Copier le numéro', copied: 'Numéro copié', noMail: 'E-mail indisponible',
      saveDisabled: 'Enregistrement des compétences non disponible sur cette page. Contactez l’administration SS97 pour mettre à jour la fiche.'},
    en: {skills: 'Skills (M365, Windows, macOS, Linux, networks, cybersecurity, cloud, backup, servers, printers)',
      down: 'Scroll down', up: 'Scroll up', copy: 'Copy ticket number', copied: 'Number copied', noMail: 'Email unavailable',
      saveDisabled: 'Saving skills is not available on this page. Contact SS97 administration to update the profile.'},
    es: {skills: 'Áreas (M365, Windows, macOS, Linux, redes, ciberseguridad, nube, copias de seguridad, servidores, impresoras)',
      down: 'Bajar', up: 'Subir', copy: 'Copiar número', copied: 'Número copiado', noMail: 'Correo no disponible',
      saveDisabled: 'No se pueden guardar las competencias en esta página. Contacte con administración SS97.'},
    ht: {skills: 'Domèn (M365, Windows, macOS, Linux, rezo, sibèsekirite, nwaj, sovgad, sèvè, enprimant)',
      down: 'Desann', up: 'Monte', copy: 'Kopye nimewo tikè a', copied: 'Nimewo a kopye', noMail: 'Imèl pa disponib',
      saveDisabled: 'Ou pa ka anrejistre konpetans sou paj sa a. Kontakte administrasyon SS97 pou mete pwofil la ajou.'}
  };

  function locale() {
    var select = document.getElementById('ss97-ws-lang');
    var lang = select ? select.value : document.documentElement.lang;
    return messages[lang] ? lang : 'fr';
  }
  function t(key) { return messages[locale()][key]; }

  function scrollMain(direction) {
    var main = document.querySelector('.ss97-tech-workspace .ws-main');
    var target = main && main.scrollHeight > main.clientHeight + 5 ? main : window;
    var distance = Math.round((main && main.clientHeight || window.innerHeight) * 0.78) * direction;
    if (typeof target.scrollBy === 'function') target.scrollBy({top: distance, behavior: 'smooth'});
  }

  function addScrollButtons() {
    if (!document.querySelector('.ss97-tech-workspace .ws-main') ||
        document.getElementById('ss97-scroll-arrows')) return;
    var controls = document.createElement('div');
    controls.id = 'ss97-scroll-arrows';
    controls.setAttribute('role', 'group');
    var up = document.createElement('button');
    var down = document.createElement('button');
    up.type = down.type = 'button';
    up.textContent = '▲';
    down.textContent = '▼';
    up.addEventListener('click', function () { scrollMain(-1); });
    down.addEventListener('click', function () { scrollMain(1); });
    controls.appendChild(up);
    controls.appendChild(down);
    document.body.appendChild(controls);
  }

  function patchProfile() {
    if (location.pathname.replace(/\/+$/, '') !== '/espace-technicien/profil') return;
    Array.prototype.forEach.call(document.querySelectorAll('.ws-main label'), function (label) {
      if (/^Domaines \(|^Skills \(|^Áreas \(|^Domèn \(/.test(label.textContent.trim())) {
        label.textContent = t('skills');
      }
    });
    // The old Web Page advertises saving through an undefined global function.
    // Never pretend the technician's edits were saved or grant write access.
    if (typeof window.ss97SaveProfile !== 'function') {
      var save = document.querySelector('button[onclick*="ss97SaveProfile"]');
      if (save && !save.dataset.ss97Warned) {
        save.dataset.ss97Warned = '1';
        save.addEventListener('click', function (event) {
          event.preventDefault();
          event.stopImmediatePropagation();
          var note = document.getElementById('ss97-profile-save-note');
          if (!note) {
            note = document.createElement('p');
            note.id = 'ss97-profile-save-note';
            note.setAttribute('role', 'status');
            save.insertAdjacentElement('afterend', note);
          }
          note.textContent = t('saveDisabled');
        }, true);
      }
    }
  }

  function safeTicket(ticket) {
    return typeof ticket === 'string' && /^ISS-[A-Za-z0-9-]{2,55}$/.test(ticket);
  }
  function patchMessages() {
    if (location.pathname.replace(/\/+$/, '') !== '/espace-technicien/messages') return;
    // Legacy Web Page onclick handlers refer to undeclared functions.
    if (typeof window.ss97OpenTicket !== 'function') {
      window.ss97OpenTicket = function (ticket) {
        if (!safeTicket(ticket)) return false;
        location.assign('/espace-technicien/intervention?ticket=' + encodeURIComponent(ticket));
        return true;
      };
    }
    if (typeof window.ss97LoadMessages !== 'function') {
      window.ss97LoadMessages = function () { location.reload(); };
    }
    Array.prototype.forEach.call(document.querySelectorAll('.ws-main a[href]'), function (link) {
      var text = link.textContent.trim();
      var href = link.getAttribute('href');
      if (/Chat interne/.test(text) && href === '/espace-technicien/dashboard') {
        link.setAttribute('href', '/espace-technicien/dashboard#ss97-tech-chat');
      }
      if (/Notifications/.test(text) && href === '/espace-technicien/dashboard#ss97-tech-notifs') {
        link.setAttribute('href', '/espace-technicien/notifications');
      }
      if (href === 'mailto:') {
        link.removeAttribute('href');
        link.setAttribute('aria-disabled', 'true');
        link.textContent = t('noMail');
      }
    });
    // Copying only the public ticket reference avoids copying client details.
    Array.prototype.forEach.call(document.querySelectorAll('.ws-main button[onclick*="ss97OpenTicket"]'), function (open) {
      if (open.dataset.ss97CopyAdded) return;
      var match = (open.getAttribute('onclick') || '').match(/ss97OpenTicket\('([^']+)'\)/);
      if (!match || !safeTicket(match[1])) return;
      open.dataset.ss97CopyAdded = '1';
      var ticket = match[1];
      var copy = document.createElement('button');
      copy.type = 'button';
      copy.className = open.className;
      copy.classList.add('ss97-copy-ticket');
      copy.textContent = t('copy');
      copy.addEventListener('click', function () {
        if (!navigator.clipboard || !navigator.clipboard.writeText) return;
        navigator.clipboard.writeText(ticket).then(function () {
          copy.textContent = t('copied');
        }).catch(function () { copy.textContent = t('copy'); });
      });
      open.insertAdjacentElement('afterend', copy);
    });
    Array.prototype.forEach.call(document.querySelectorAll('.ss97-copy-ticket'), function (button) {
      // Avoid a MutationObserver loop: do not rewrite unchanged text.
      if (button.textContent !== t('copied') && button.textContent !== t('copy')) {
        button.textContent = t('copy');
      }
    });
  }

  function localizeScrollButtons() {
    var arrows = document.getElementById('ss97-scroll-arrows');
    if (!arrows) return;
    var buttons = arrows.querySelectorAll('button');
    if (buttons[0]) { buttons[0].title = t('up'); buttons[0].setAttribute('aria-label', t('up')); }
    if (buttons[1]) { buttons[1].title = t('down'); buttons[1].setAttribute('aria-label', t('down')); }
  }
  function apply() { addScrollButtons(); localizeScrollButtons(); patchProfile(); patchMessages(); }
  function boot() {
    apply();
    var select = document.getElementById('ss97-ws-lang');
    if (select) select.addEventListener('change', apply);
    window.addEventListener('ss97:tech-ready', apply);
    // Legacy Web Page content can load after the shell finishes.
    setTimeout(apply, 350);
    setTimeout(apply, 1400);
    var messagesList = document.getElementById('ws-messages');
    if (messagesList && typeof MutationObserver === 'function') {
      var observer = new MutationObserver(patchMessages);
      observer.observe(messagesList, {childList:true, subtree:true});
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once:true});
  else boot();
})();
