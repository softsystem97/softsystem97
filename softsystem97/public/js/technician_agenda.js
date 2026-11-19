/* Technician agenda: one server-scoped source of truth, and no endless loader. */
(function () {
  'use strict';
  if (location.pathname.replace(/\/+$/, '') !== '/espace-technicien/agenda') return;
  if (window.__ss97TechAgendaV1) return;
  window.__ss97TechAgendaV1 = true;

  var endpoint = '/api/method/softsystem97.portal.technician_agenda.get_my_agenda';
  var translations = {
    fr: {
      title: 'Mes interventions planifiées', empty: 'Aucune intervention planifiée pour le moment.',
      help: 'Les rendez-vous apparaissent ici lorsqu’une date est enregistrée sur un ticket qui vous est attribué.',
      error: 'Impossible de charger l’agenda. Vérifiez votre connexion puis réessayez.',
      forbidden: 'Votre session technicien doit être vérifiée pour consulter cet agenda.',
      retry: 'Réessayer', tickets: 'Voir mes tickets', open: 'Ouvrir le ticket',
      loading: 'Chargement des rendez-vous…', appointment: 'Rendez-vous'
    },
    en: {
      title: 'My scheduled interventions', empty: 'No interventions are scheduled yet.',
      help: 'Appointments appear here when a date is set on a ticket assigned to you.',
      error: 'Could not load the schedule. Check your connection and try again.',
      forbidden: 'Your technician session must be verified to view this schedule.',
      retry: 'Try again', tickets: 'View my tickets', open: 'Open ticket',
      loading: 'Loading appointments…', appointment: 'Appointment'
    },
    es: {
      title: 'Mis intervenciones programadas', empty: 'Todavía no hay intervenciones programadas.',
      help: 'Las citas aparecen aquí cuando se establece una fecha en un ticket asignado a usted.',
      error: 'No se pudo cargar la agenda. Compruebe su conexión y vuelva a intentarlo.',
      forbidden: 'Debe verificarse su sesión de técnico para consultar esta agenda.',
      retry: 'Reintentar', tickets: 'Ver mis tickets', open: 'Abrir ticket',
      loading: 'Cargando citas…', appointment: 'Cita'
    },
    ht: {
      title: 'Entèvansyon mwen ki planifye', empty: 'Pa gen entèvansyon ki planifye pou kounye a.',
      help: 'Randevou yo parèt isit lè yo mete yon dat sou yon tikè yo ba ou.',
      error: 'Nou pa ka chaje kalandriye a. Verifye koneksyon ou epi eseye ankò.',
      forbidden: 'Yo dwe verifye sesyon teknisyen ou pou ou ka wè kalandriye sa a.',
      retry: 'Eseye ankò', tickets: 'Gade tikè mwen yo', open: 'Louvri tikè a',
      loading: 'Ap chaje randevou yo…', appointment: 'Randevou'
    }
  };
  var currentEntries = null;
  var lastError = '';
  var loading = false;
  var booted = false;

  function language() {
    var select = document.getElementById('ss97-ws-lang');
    var value = select && select.value || document.documentElement.lang || 'fr';
    return translations[value] ? value : 'fr';
  }
  function label(key) { return translations[language()][key]; }
  function element(tag, text, className) {
    var node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function link(text, href) {
    var node = element('a', text, 'ss97-agenda-link');
    node.href = href;
    node.style.cssText = 'display:inline-block;padding:8px 12px;border:1px solid #64c9e8;border-radius:7px;margin:8px 8px 0 0;color:inherit;';
    return node;
  }
  function render() {
    var box = document.getElementById('ag-box');
    if (!box) return;
    box.replaceChildren();
    box.setAttribute('aria-live', 'polite');
    box.appendChild(element('h2', label('title')));
    if (loading) { box.appendChild(element('p', label('loading'))); return; }
    if (lastError) {
      box.appendChild(element('p', label(lastError), 'ss97-agenda-error'));
      var retry = element('button', label('retry'));
      retry.type = 'button';
      retry.addEventListener('click', load);
      box.appendChild(retry);
      return;
    }
    var entries = currentEntries || [];
    if (!entries.length) {
      box.appendChild(element('p', label('empty')));
      box.appendChild(element('p', label('help'), 'muted'));
      box.appendChild(link(label('tickets'), '/espace-technicien/tickets'));
      return;
    }
    var list = element('ul');
    list.style.cssText = 'list-style:none;padding:0;margin:16px 0;display:grid;gap:12px;';
    entries.forEach(function (entry) {
      if (!entry || !entry.ticket) return;
      var item = element('li');
      item.style.cssText = 'padding:14px;border:1px solid rgba(153,205,228,.45);border-radius:10px;';
      var date = new Date(entry.starts_at);
      var dateText = isNaN(date.getTime()) ? String(entry.starts_at) :
        date.toLocaleString(language() === 'ht' ? 'fr-HT' : language(), {dateStyle:'medium',timeStyle:'short'});
      item.appendChild(element('strong', dateText + ' · ' + entry.ticket));
      item.appendChild(element('p', entry.subject || label('appointment')));
      if (entry.status) item.appendChild(element('small', entry.status));
      item.appendChild(element('div')).appendChild(
        link(label('open'), '/espace-technicien/intervention?ticket=' + encodeURIComponent(entry.ticket))
      );
      list.appendChild(item);
    });
    box.appendChild(list);
  }
  function load() {
    if (loading) return;
    loading = true;
    lastError = '';
    render();
    var controller = typeof AbortController === 'function' ? new AbortController() : null;
    var timeout = controller && setTimeout(function () { controller.abort(); }, 12000);
    fetch(endpoint, {
      credentials: 'same-origin', headers: {'Accept':'application/json'},
      signal: controller ? controller.signal : undefined
    }).then(function (response) {
      if (response.status === 401 || response.status === 403) throw Error('forbidden');
      if (!response.ok) throw Error('network');
      return response.json();
    }).then(function (payload) {
      if (!payload || !payload.message || !Array.isArray(payload.message.entries)) throw Error('network');
      currentEntries = payload.message.entries;
    }).catch(function (error) {
      currentEntries = null;
      lastError = error.message === 'forbidden' ? 'forbidden' : 'error';
    }).finally(function () {
      if (timeout) clearTimeout(timeout);
      loading = false;
      render();
    });
  }
  function boot() {
    if (booted || !document.getElementById('ag-box')) return;
    booted = true;
    var select = document.getElementById('ss97-ws-lang');
    if (select) select.addEventListener('change', render);
    load();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once:true});
  else boot();
})();
