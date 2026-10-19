/* Session cookies and native CSRF protection; no token storage or password logging. */
(() => {
  'use strict';
  const el = id => document.getElementById(`ss97-${id}`);
  const error = message => { el('error').textContent = message; };
  const prefix = '/api/method/softsystem97.integrations.ticket_bridge.api.';
  async function request(method, args = {}, mutate = false, nativeLogin = false) {
    const url = nativeLogin ? '/api/method/login' : prefix + method;
    const response = await fetch(mutate ? url : `${url}?${new URLSearchParams(args)}`, {
      method: mutate ? 'POST' : 'GET', credentials: 'same-origin', redirect: 'error',
      headers: mutate ? { 'Content-Type': 'application/x-www-form-urlencoded',
        'X-Frappe-CSRF-Token': frappe.csrf_token } : {},
      body: mutate ? new URLSearchParams(args) : undefined
    });
    if (!response.ok) {
      // Never display server traceback/error bodies, or reveal whether a foreign ticket exists.
      throw new Error(response.status === 401 ? 'Session expirée. Reconnectez-vous.' :
        response.status === 403 ? 'Accès refusé. Vérifiez votre compte et vos affectations.' :
        response.status === 409 ? 'Le ticket a changé. Actualisez avant de réessayer.' :
        'Opération refusée ou service indisponible. Actualisez puis réessayez.');
    }
    return (await response.json()).message;
  }
  if (el('login')) {
    const password = el('password'), toggle = el('show-password');
    let timeout;
    function hide() { clearTimeout(timeout); password.type = 'password'; toggle.textContent = 'Afficher le mot de passe'; toggle.setAttribute('aria-pressed', 'false'); }
    toggle.onclick = () => {
      if (password.type === 'text') return hide();
      password.type = 'text'; toggle.textContent = 'Masquer le mot de passe'; toggle.setAttribute('aria-pressed', 'true');
      timeout = setTimeout(hide, 10000);
    };
    window.addEventListener('blur', hide);
    el('login').onsubmit = async event => {
      event.preventDefault(); hide(); error('');
      const button = event.submitter; button.disabled = true;
      try {
        const result = await request('', { usr: el('email').value, pwd: password.value }, true, true);
        password.value = '';
        if (result === 'Logged In') window.location.replace('/ss97-dev-technician');
        else { error('Poursuivez avec la connexion Frappe pour terminer l’authentification.'); }
      } catch (err) { password.value = ''; error(err.message); }
      finally { button.disabled = false; }
    };
    return;
  }
  if (!el('workspace')) return;
  let current, offset = 0;
  const audience = () => el('audience').value;
  async function key(action, payload) {
    // Retain only an opaque key + payload hash across a reload, never form contents.
    const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify([action, payload])));
    const fingerprint = [...new Uint8Array(bytes)].map(byte => byte.toString(16).padStart(2, '0')).join('');
    const storageKey = `ss97-bridge:${fingerprint}`;
    let request_id = sessionStorage.getItem(storageKey);
    if (!request_id) { request_id = crypto.randomUUID(); sessionStorage.setItem(storageKey, request_id); }
    return { request_id, storageKey };
  }
  function clearDetail() {
    current = null; el('detail').hidden = true; el('history').replaceChildren();
    for (const field of ['title', 'body', 'status']) el(field).textContent = '';
    el('status-choice').replaceChildren();
  }
  async function detail(name) {
    clearDetail();
    const result = await request('get_ticket', { name, audience: audience() });
    current = result.ticket;
    el('title').textContent = `${current.name} — ${current.subject}`;
    el('body').textContent = current.description;
    el('status').textContent = current.status;
    el('status-choice').replaceChildren(...current.allowed_statuses.map(status => new Option(status, status)));
    el('status-form').hidden = !current.allowed_statuses.length;
    el('comment').hidden = current.status === 'Closed';
    el('history').replaceChildren(...result.history.map(row => {
      const item = document.createElement('p'); item.textContent = `${row.creation} — ${row.detail}`; return item;
    }));
    el('detail').hidden = false;
  }
  async function refresh() {
    error(''); clearDetail(); el('tickets').replaceChildren(); el('notifications').replaceChildren();
    el('create').hidden = audience() !== 'client';
    const result = await request('list_tickets', { audience: audience(), offset });
    el('previous').disabled = offset === 0; el('next').disabled = result.tickets.length < 50;
    if (!result.tickets.length) el('tickets').textContent = 'Aucun ticket accessible.';
    for (const row of result.tickets) {
      const article = document.createElement('article'), button = document.createElement('button');
      button.type = 'button'; button.textContent = `${row.name} — ${row.subject} — ${row.status}`;
      button.onclick = () => detail(row.name).catch(err => { clearDetail(); error(err.message); });
      article.append(button); el('tickets').append(article);
    }
    const notices = await request('get_notifications', { audience: audience() });
    for (const notice of notices.notifications) {
      const item = document.createElement('p'); item.textContent = `${notice.title} — ${notice.message}`; el('notifications').append(item);
    }
  }
  const run = fn => fn().catch(err => error(err.message));
  el('refresh').onclick = () => run(refresh);
  el('audience').onchange = () => { offset = 0; run(refresh); };
  el('previous').onclick = () => { offset = Math.max(0, offset - 50); run(refresh); };
  el('next').onclick = () => { offset += 50; run(refresh); };
  for (const [form, method, args] of [
    ['create', 'create_ticket', () => ({ subject: el('subject').value, description: el('description').value })],
    ['status-form', 'update_status', () => ({ name: current.name, status: el('status-choice').value, expected_modified: current.modified })],
    ['comment', 'add_intervention', () => ({ name: current.name, content: el('content').value, audience: audience() })]
  ]) {
    el(form).onsubmit = async event => {
      event.preventDefault(); error(''); const button = event.submitter; button.disabled = true;
      try {
        const payload = args(), { request_id, storageKey } = await key(method, payload);
        const result = await request(method, { ...payload, request_id }, true);
        sessionStorage.removeItem(storageKey);
        el(form).reset(); await refresh(); if (result.name) await detail(result.name);
      } catch (err) { error(err.message); }
      finally { button.disabled = false; }
    };
  }
  run(refresh);
})();
