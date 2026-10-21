"""Scoped shell for the existing recovered tickets page; no redirect or remote agent."""


def open_shell(active):
    return '<main class="ss97-tech-workspace"><nav><a href="/espace-technicien/tickets">Mes tickets</a> · <a href="/logout">Déconnexion</a></nav>'


def close_shell():
    return '</main>'
