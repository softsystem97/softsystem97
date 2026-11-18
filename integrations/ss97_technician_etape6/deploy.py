"""Recovered tickets page builder only; no deployment or import side effects."""

def page_tickets(P) -> str:
    """Mes tickets — shell métier + filtres / JS dashboard existants."""
    from integrations.ss97_technician_operations.technician_guard import technician_login_required_html
    from integrations.ss97_technician_operations.workspace_shell import close_shell, open_shell

    login = technician_login_required_html(section_title="Mes interventions")
    return f"""
<div class="ss97-tech">{P.TECH_CSS}
{open_shell("tickets")}
<div class="wrap">
  <div class="hero">
    <p class="pillrow"><span class="pill">SoftSystem97</span><span class="pill">Mes tickets</span></p>
    <h1 class="brand">Mes tickets</h1>
    <p class="sub">Tickets qui vous sont affectés — accepter, ouvrir le cockpit, suivre l'intervention.</p>
  </div>
  {login}
  <div data-tech-private style="display:none">
  <div data-tech-user>
    <div id="ss97-dash-error" class="error-banner" role="alert" style="display:none"></div>
    <p class="muted">Technicien : <strong id="ss97-tech-user" style="color:#fff"></strong></p>
    {P._presence_bar()}
    {P._kpi_block()}
    {P._ticket_tables()}
    <div class="btns" style="margin-top:14px">
      <a class="btn btn-p" href="/ss97-tech-missions">Workflow missions</a>
      <a class="btn btn-g" href="/espace-technicien/dashboard">Dashboard</a>
    </div>
    <div id="ss97-cal" style="display:none"></div>
    <div id="ss97-tech-profile" style="display:none"></div>
    <div id="ss97-tech-profile-extra" style="display:none"></div>
    <div id="ss97-tech-skills" style="display:none"></div>
    <div id="ss97-tech-notifs" style="display:none"></div>
    <div id="ss97-tech-toolbox" style="display:none"></div>
    <div id="ss97-tech-docs" style="display:none"></div>
    <div id="ss97-tech-activity" style="display:none"></div>
    <div id="ss97-tech-remote" style="display:none"></div>
    <div id="tbl-missions" style="display:none"></div>
  </div>
  </div>
</div>
{P.TECH_DASH_JS}
{close_shell()}
</div>
"""
