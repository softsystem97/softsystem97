/* SS97 V1 remote session coordination, intentionally no desktop streaming. */
(() => {
  'use strict';
  const $ = id => document.getElementById('remote-' + id);
  if (!$('prepare')) return;
  const prefix = '/api/method/softsystem97.remote.api.';
  let current = null;
  let audience = 'client';

  function message(text) { $('message').textContent = text; }
  async function call(method, args, write = false) {
    const url = prefix + method + (write ? '' : '?' + new URLSearchParams(args));
    const response = await fetch(url, {
      method: write ? 'POST' : 'GET', credentials: 'same-origin', redirect: 'error',
      headers: write ? { 'Content-Type': 'application/x-www-form-urlencoded',
        'X-Frappe-CSRF-Token': frappe.csrf_token } : {},
      body: write ? new URLSearchParams(args) : undefined,
    });
    if (!response.ok) {
      throw Error(response.status === 403 ? 'Accès non autorisé ou demande expirée.' :
        'Opération indisponible. Vérifiez votre connexion et votre ticket.');
    }
    return (await response.json()).message;
  }
  const act = async (button, fn) => {
    button.disabled = true; message('');
    try { await fn(); } catch (error) { message(error.message); }
    finally { button.disabled = false; }
  };
  function showSession(session, asAudience) {
    current = session.session_id;
    audience = asAudience;
    $('status-panel').hidden = false;
    $('status').textContent = 'Ticket ' + session.ticket_name +
      ' — état : ' + session.state + ' — expiration : ' + session.expires_at;
    $('stop').hidden = ['DECLINED','ENDED','EXPIRED','ERROR'].includes(session.state);
    $('client-session').hidden = asAudience !== 'client' || session.state !== 'CLIENT_READY';
    $('client-details').textContent = 'Technicien : ' + session.technician +
      ' — ticket : ' + session.ticket_name;
  }
  $('prepare').onsubmit = event => {
    event.preventDefault();
    act(event.submitter, async () => {
      const session = await call('prepare_session', { ticket_name: $('ticket').value.trim() }, true);
      $('code').textContent = session.join_code;
      $('code-panel').hidden = false;
      showSession(session, 'technician');
      message(session.invite_email_requested ?
        'Session préparée. Invitation e-mail demandée, livraison non confirmée. Aucun contrôle à distance n’est ouvert.' :
        'Session préparée. Communiquez le code au client par un canal convenu. Aucun contrôle à distance n’est ouvert.');
    });
  };
  $('join').onsubmit = event => {
    event.preventDefault();
    act(event.submitter, async () => {
      const session = await call('join_session', { join_code: $('join-code').value }, true);
      $('join-code').value = '';
      showSession(session, 'client');
      message('Code reconnu : vérifiez l’identité du technicien avant d’accepter.');
    });
  };
  async function decide(approve, button) {
    if (!current) return;
    await act(button, async () => {
      const session = await call('decide_session', { session_id: current, approve: approve ? '1' : '0' }, true);
      showSession(session, 'client');
      message(approve ? 'Accord portail enregistré. Le contrôle écran reste désactivé.' : 'Assistance refusée.');
    });
  }
  $('approve').onclick = () => decide(true, $('approve'));
  $('decline').onclick = () => decide(false, $('decline'));
  $('refresh').onclick = () => {
    if (!current) return;
    act($('refresh'), async () => showSession(await call('get_session',
      { session_id: current, audience }), audience));
  };
  $('stop').onclick = () => {
    if (!current) return;
    act($('stop'), async () => {
      const session = await call('end_session', { session_id: current, audience }, true);
      showSession(session, audience);
      message('Demande terminée.');
    });
  };
})();
