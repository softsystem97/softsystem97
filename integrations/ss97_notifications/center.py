"""Historical notification presentation with bounded, read-only bridge access.

Legacy generic ToDo/User mutations and SDK producers are deliberately excluded.
"""

from urllib.parse import quote, unquote, urlsplit

TECH_ALLOWED_ROUTE_PREFIXES = (
    "/espace-technicien/dashboard",
    "/espace-technicien/tableau-de-bord",
    "/espace-technicien/tickets",
    "/espace-technicien/intervention",
    "/espace-technicien/boite-a-outils",
    "/espace-technicien/centre-stabilite",
    "/espace-technicien/messages",
    "/espace-technicien/agenda",
    "/espace-technicien/rapports",
    "/espace-technicien/historique",
    "/espace-technicien/notifications",
    "/espace-technicien/profil",
)

TECH_EVENT_ROUTES = {
    "assigned": "intervention",
    "accepted": "intervention",
    "started": "intervention",
    "paused": "intervention",
    "resumed": "intervention",
    "urgent": "intervention",
    "payment": "intervention",
    "validation": "intervention",
    "message": "messages",
    "action_client": "intervention",
    "report": "rapports",
    "report_complete": "rapports",
    "report_validated": "rapports",
    "report_refused": "rapports",
    "report_pending": "rapports",
    "agenda": "agenda",
    "appointment": "agenda",
    "responsable": "intervention",
    "securite": "intervention",
    "security": "intervention",
    "tool": "boite-a-outils",
    "closed": "historique",
    "resolved": "historique",
    "history": "historique",
}

NOTIF_BELL_CSS = """
<style>
.ss97-bell-wrap{position:fixed;top:14px;right:16px;z-index:10050;font-family:Sora,system-ui,sans-serif}
.ss97-bell-btn{position:relative;width:46px;height:46px;border-radius:50%;border:1px solid rgba(125,211,252,.35);
  background:rgba(8,18,32,.92);color:#e2e8f0;cursor:pointer;font-size:1.15rem;display:flex;align-items:center;justify-content:center}
.ss97-bell-btn:hover{border-color:#38bdf8}
.ss97-bell-count{position:absolute;top:-4px;right:-4px;min-width:18px;height:18px;padding:0 5px;border-radius:999px;
  background:#ef4444;color:#fff;font-size:.68rem;font-weight:700;display:none;align-items:center;justify-content:center;line-height:18px}
.ss97-bell-count.on{display:inline-flex}
.ss97-bell-panel{display:none;position:absolute;top:54px;right:0;width:min(400px,94vw);max-height:78vh;overflow:auto;
  background:#0b1626;border:1px solid rgba(125,211,252,.25);border-radius:14px;box-shadow:0 16px 40px rgba(0,0,0,.45);padding:10px}
.ss97-bell-panel.open{display:block}
.ss97-bell-panel h4{margin:4px 8px 10px;color:#fff;font-size:.92rem}
.ss97-bell-item{padding:10px;border-radius:10px;border:1px solid rgba(148,163,184,.12);margin:6px 0;background:rgba(15,23,42,.55)}
.ss97-bell-item.unread{border-left:3px solid #38bdf8}
.ss97-bell-item .t{color:#fff;font-size:.84rem;font-weight:600}
.ss97-bell-item .m{color:#94a3b8;font-size:.72rem;margin-top:4px}
.ss97-bell-item .evt{color:#7dd3fc;font-size:.7rem;margin-top:4px;text-transform:uppercase;letter-spacing:.04em}
.ss97-bell-item .acts{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.ss97-bell-item .acts button{font-size:.7rem;padding:6px 10px;border-radius:8px;border:1px solid rgba(56,189,248,.35);
  background:rgba(14,165,233,.18);color:#e0f2fe;cursor:pointer}
.ss97-bell-item .acts button.sec{border-color:rgba(255,255,255,.18);background:rgba(255,255,255,.06);color:#e2e8f0}
.ss97-bell-actions{display:flex;flex-wrap:wrap;gap:6px;margin:8px}
.ss97-bell-actions button,.ss97-bell-filters button{font-size:.72rem;padding:6px 10px;border-radius:8px;border:1px solid rgba(255,255,255,.18);
  background:rgba(255,255,255,.06);color:#e2e8f0;cursor:pointer}
.ss97-bell-filters{display:flex;flex-wrap:wrap;gap:6px;margin:4px 8px 8px}
.ss97-bell-filters button.on{border-color:#38bdf8;background:rgba(56,189,248,.18);color:#fff}
.ss97-bell-search{width:100%;margin:4px 8px 8px;padding:8px;border-radius:8px;border:1px solid rgba(125,211,252,.2);
  background:#07111d;color:#e2e8f0;box-sizing:border-box}
@media(max-width:575px){
  .ss97-bell-wrap{top:10px;right:10px}
  .ss97-bell-btn{width:44px;height:44px;min-height:44px}
  .ss97-bell-panel{width:min(100vw - 20px, 400px)}
}
</style>
"""


def sanitize_tech_route(route: str | None, *, ticket: str = '', event: str = '') -> str:
    """Keep historical event routing, reject external or ambiguous URL paths."""
    fallback = '/espace-technicien/dashboard'
    raw = (route or '').strip()
    if raw:
        if any(ord(c) < 32 for c in raw) or '\\' in raw:
            return fallback
        try:
            parsed = urlsplit(raw)
            if parsed.scheme or parsed.netloc:
                if parsed.scheme != 'https' or parsed.netloc not in (
                    'app.softsystem97.com', 'softsystem97.com',
                ):
                    return fallback
            path = unquote(parsed.path)
            if '%' in path or '\\' in path or any(ord(c) < 32 for c in path):
                return fallback
            if any(part in ('.', '..') for part in path.split('/')):
                return fallback
            if path.rstrip('/') not in TECH_ALLOWED_ROUTE_PREFIXES:
                return fallback
            # Keep the local form only. Reject HTML/URL attribute injection.
            if any(c in raw for c in ('"', "'", '<', '>')):
                return fallback
            return parsed.path + ('?' + parsed.query if parsed.query else '')
        except ValueError:
            return fallback
    kind = TECH_EVENT_ROUTES.get((event or '').strip().lower(), '')
    if not kind:
        kind = 'intervention' if ticket else 'dashboard'
    query = '?ticket=' + quote(str(ticket), safe='') if ticket else ''
    section = {'action_client': 'action-client', 'responsable': 'responsable',
               'securite': 'securite', 'security': 'securite'}.get((event or '').lower())
    if section:
        query += ('&' if query else '?') + 'section=' + section
    return '/espace-technicien/' + kind + query


def tech_route_for_event(event: str, ticket_name: str) -> str:
    return sanitize_tech_route('', ticket=ticket_name or '', event=event or '')


NOTIF_BELL_JS = r"""
<script>
(function(){
  if(window.__ss97ScopedNotifications) return;
  window.__ss97ScopedNotifications=true;
  var root=document.createElement('section');
  root.setAttribute('aria-label','Notifications technicien');
  var button=document.createElement('button');
  button.type='button';button.textContent='Charger mes notifications';
  var list=document.createElement('ul');
  root.appendChild(button);root.appendChild(list);
  var host=document.querySelector('[data-tech-private]');
  if(!host)return;
  host.appendChild(root);
  button.addEventListener('click',async function(){
    list.replaceChildren();button.disabled=true;
    try{
      var response=await fetch('/api/method/softsystem97.integrations.ticket_bridge.api.get_notifications?audience=technician',
        {credentials:'same-origin',headers:{'Accept':'application/json'},cache:'no-store'});
      if(!response.ok)throw new Error('denied');
      var payload=await response.json();
      if(payload.exc||!payload.message||!Array.isArray(payload.message.notifications))throw new Error('invalid');
      payload.message.notifications.forEach(function(item){
        var row=document.createElement('li');var link=document.createElement('a');
        link.textContent=String(item.title||'Notification');
        link.href='/espace-technicien/intervention?ticket='+encodeURIComponent(item.reference_name||'');
        row.appendChild(link);list.appendChild(row);
      });
    }catch(error){list.replaceChildren();list.textContent='Notifications indisponibles. Vérifiez votre session et vos autorisations.';}
    finally{button.disabled=false;}
  });
})();
</script>
"""


def notif_assets() -> str:
    """Read-only notifications; the existing bridge enforces current ticket scope."""
    return NOTIF_BELL_CSS + NOTIF_BELL_JS
