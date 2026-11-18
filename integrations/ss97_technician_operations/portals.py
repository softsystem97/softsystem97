"""Adapters for the recovered page_tickets(P) contract; no deployment on import."""
from integrations.ss97_notifications.center import notif_assets
from integrations.ss97_technician_operations.dashboard_js import build_tech_dash_js
from integrations.ss97_website.mission5_recruit import THEME

TECH_CSS = THEME + '''<style>
.ss97-tech{background:#07111d;color:#e2e8f0;padding:16px;font:16px system-ui;min-height:90vh}
.ss97-tech .wrap{max-width:1150px;margin:auto}.ss97-tech button,.ss97-tech select,.ss97-tech textarea{font:inherit;margin:6px;padding:10px;max-width:100%}
.ss97-tech button:disabled{opacity:.5}.ss97-tech a{color:#38bdf8}.ss97-tech table{width:100%;border-collapse:collapse}.ss97-tech td,.ss97-tech th{padding:10px;text-align:left;border-bottom:1px solid #475569}
.ss97-tech textarea{display:block;width:95%;min-height:110px}.ss97-tech .table-scroll{overflow-x:auto}.ss97-tech [hidden]{display:none!important}
@media(max-width:600px){.ss97-tech{padding:8px}.ss97-tech td,.ss97-tech th{padding:6px}.ss97-tech button{width:95%}}
</style>'''
TECH_DASH_JS = build_tech_dash_js() + notif_assets()


def _presence_bar():
    return '<p>Présence et supervision distante non activées.</p>'


def _kpi_block():
    return '<p id="ss97-ticket-count" aria-live="polite"></p>'


def _ticket_tables():
    return '''
<button id="ss97-refresh" type="button">Actualiser mes tickets</button>
<div class="table-scroll"><table><thead><tr><th>Ticket</th><th>Sujet</th><th>Statut</th><th>Priorité</th><th>Action</th></tr></thead><tbody id="ss97-ticket-rows"></tbody></table></div>
<button id="ss97-previous" type="button" disabled>Page précédente</button><button id="ss97-next" type="button" disabled>Page suivante</button>
<section id="ss97-detail" hidden>
<h2 id="ss97-detail-title"></h2><p id="ss97-detail-description"></p><p id="ss97-detail-status"></p>
<button type="button" disabled title="Autorisation métier d’acceptation non raccordée">Accepter</button>
<button type="button" disabled title="Autorisation métier de démarrage non raccordée">Démarrer</button>
<button type="button" disabled title="Workflow de clôture non validé">Demander une clôture</button>
<label>Statut candidat (validation serveur obligatoire)<select id="ss97-status"></select></label><button id="ss97-update" type="button">Demander le changement de statut</button>
<label>Compte rendu<textarea id="ss97-report" maxlength="5000"></textarea></label><button id="ss97-save-report" type="button">Enregistrer le compte rendu</button>
<button id="ss97-history-refresh" type="button">Actualiser l’historique</button><ol id="ss97-history"></ol>
</section>
<p id="ss97-operation-result" role="status"></p>'''
