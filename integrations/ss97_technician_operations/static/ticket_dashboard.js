(function () {
  'use strict';
  if (window.__ss97ScopedDashboard) return;
  window.__ss97ScopedDashboard = true;
  const base = '/api/method/softsystem97.integrations.ticket_bridge.api.';
  let current = null, offset = 0, epoch = 0, busy = false;
  const pending = new Map();
  const byId = id => document.getElementById(id);
  const text = (id, value) => { const el = byId(id); if (el) el.textContent = String(value || ''); };
  const result = message => text('ss97-operation-result', message);
  function clearDetail() {
    current = null;
    byId('ss97-detail').hidden = true;
    ['ss97-detail-title', 'ss97-detail-description', 'ss97-detail-status'].forEach(id => text(id, ''));
    byId('ss97-history').replaceChildren();
    byId('ss97-status').replaceChildren();
    byId('ss97-report').value = '';
  }
  function deny() {
    epoch += 1; window.__ss97AccessEpoch = (window.__ss97AccessEpoch || 0) + 1; pending.clear(); clearDetail();
    byId('ss97-ticket-rows').replaceChildren();
    text('ss97-tech-user', ''); text('ss97-ticket-count', '');
    document.querySelectorAll('[data-tech-private]').forEach(el => { el.style.display = 'none'; });
    document.querySelectorAll('[data-ss97-notifications]').forEach(el => el.replaceChildren());
    byId('ss97-login-required').hidden = false;
    byId('ss97-login-required').textContent = 'Session expirée ou accès refusé. Reconnectez-vous via /login.';
    byId('ss97-previous').disabled = true; byId('ss97-next').disabled = true;
  }
  window.ss97ScopedAccessDenied = deny;
  async function rpc(method, args = {}, write = false) {
    const options = {credentials: 'same-origin', cache: 'no-store', headers: {Accept: 'application/json'}};
    let url = base + method;
    if (write) {
      const csrf = window.frappe && window.frappe.csrf_token;
      if (!csrf || csrf === 'None') throw new Error('Jeton CSRF absent. Rechargez la page.');
      const key = JSON.stringify([method, args]);
      if (!pending.has(key)) pending.set(key, window.crypto.randomUUID());
      options.method = 'POST';
      options.headers['Content-Type'] = 'application/json';
      options.headers['X-Frappe-CSRF-Token'] = csrf;
      options.body = JSON.stringify({...args, request_id: pending.get(key)});
      options.pendingKey = key;
    } else { url += '?' + new URLSearchParams(args).toString(); }
    const response = await fetch(url, options);
    if ([401, 403].includes(response.status)) {
      deny(); throw new Error('Session expirée ou accès refusé.');
    }
    let payload;
    try { payload = await response.json(); } catch (error) { throw new Error('Réponse serveur invalide.'); }
    if ([401, 403].includes(response.status) || ['PermissionError', 'AuthenticationError', 'SessionExpired'].includes(payload.exc_type)) {
      deny(); throw new Error('Session expirée ou accès refusé.');
    }
    if (response.status === 409 || payload.exc_type === 'TimestampMismatchError' || payload.exc_type === 'BridgeConflict') {
      clearDetail(); pending.delete(options.pendingKey);
      throw new Error('Conflit : rechargez le ticket avant toute nouvelle modification.');
    }
    if (!response.ok || payload.exc || payload.exception || !Object.prototype.hasOwnProperty.call(payload, 'message')) {
      throw new Error('Opération refusée ou indisponible. Aucune réussite confirmée.');
    }
    if (write) pending.delete(options.pendingKey);
    return payload.message;
  }
  async function run(work) {
    if (busy) return;
    busy = true;
    document.querySelectorAll('[data-scoped-action]').forEach(el => { el.disabled = true; });
    try { await work(); } catch (error) { result(error.message || 'Opération indisponible.'); }
    finally {
      busy = false;
      document.querySelectorAll('[data-scoped-action]').forEach(el => { el.disabled = false; });
      byId('ss97-update').disabled = !current || !byId('ss97-status').options.length;
      byId('ss97-save-report').disabled = !current || current.can_add_intervention !== true;
    }
  }
  async function load() {
    const generation = ++epoch;
    clearDetail(); byId('ss97-ticket-rows').replaceChildren();
    const session = await rpc('session_info', {audience: 'technician', commercial: '1'});
    const data = await rpc('list_tickets', {audience: 'technician', offset});
    if (generation !== epoch) return;
    if (!session || !session.user || !data || !Array.isArray(data.tickets)) throw new Error('Données serveur invalides.');
    text('ss97-tech-user', session.user);
    byId('ss97-login-required').hidden = true;
    document.querySelectorAll('[data-tech-private]').forEach(el => { el.style.display = 'block'; });
    data.tickets.forEach(ticket => {
      const row = document.createElement('tr');
      [ticket.name, ticket.subject, ticket.status, ticket.priority].forEach(value => {
        const cell = document.createElement('td'); cell.textContent = String(value || ''); row.appendChild(cell);
      });
      const cell = document.createElement('td'), button = document.createElement('button');
      button.type = 'button'; button.textContent = 'Ouvrir l’intervention';
      button.addEventListener('click', () => run(() => detail(ticket.name)));
      cell.appendChild(button); row.appendChild(cell); byId('ss97-ticket-rows').appendChild(row);
    });
    text('ss97-ticket-count', data.tickets.length + ' ticket(s) sur cette page');
    byId('ss97-previous').disabled = offset === 0;
    byId('ss97-next').disabled = data.tickets.length < data.page_size;
    result('Liste actualisée.');
  }
  async function detail(name) {
    const generation = ++epoch;
    clearDetail();
    const data = await rpc('get_ticket', {name, audience: 'technician', commercial: '1'});
    if (generation !== epoch) return;
    if (!data || !data.ticket || !Array.isArray(data.history)) throw new Error('Détail serveur invalide.');
    current = data.ticket;
    text('ss97-detail-title', current.name + ' — ' + current.subject);
    text('ss97-detail-description', current.description);
    text('ss97-detail-status', current.status + ' · ' + (current.priority || ''));
    (current.allowed_statuses || []).forEach(status => {
      const option = document.createElement('option'); option.value = status; option.textContent = status;
      byId('ss97-status').appendChild(option);
    });
    data.history.forEach(event => {
      const item = document.createElement('li');
      item.textContent = [event.creation, event.action, event.detail].join(' — ');
      byId('ss97-history').appendChild(item);
    });
    byId('ss97-detail').hidden = false;
    result('Ticket chargé. Toute modification reste soumise à la décision du serveur.');
  }
  function bind(id, work) {
    const element = byId(id); element.setAttribute('data-scoped-action', '1');
    element.addEventListener('click', () => run(work));
  }
  bind('ss97-refresh', load);
  byId('ss97-previous').addEventListener('click', () => run(async () => { offset = Math.max(0, offset - 50); await load(); }));
  byId('ss97-next').addEventListener('click', () => run(async () => { offset += 50; await load(); }));
  bind('ss97-history-refresh', async () => { if (current) await detail(current.name); });
  bind('ss97-update', async () => {
    if (!current || !byId('ss97-status').value) return;
    const name = current.name;
    const response = await rpc('update_status', {name, status: byId('ss97-status').value, expected_modified: current.modified}, true);
    if (!response || response.name !== name) throw new Error('Résultat de modification invalide.');
    await detail(name); result('Statut enregistré et ticket rechargé.');
  });
  bind('ss97-save-report', async () => {
    if (!current || current.can_add_intervention !== true) return;
    const content = byId('ss97-report').value.trim();
    if (!content) throw new Error('Compte rendu requis.');
    const name = current.name;
    const response = await rpc('add_intervention', {name, content, audience: 'technician'}, true);
    if (!response || response.name !== name) throw new Error('Résultat de compte rendu invalide.');
    await detail(name); result('Compte rendu enregistré dans l’historique.');
  });
  run(load);
})();
