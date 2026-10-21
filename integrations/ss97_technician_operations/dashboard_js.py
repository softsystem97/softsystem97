"""Commercial dashboard adapter: only scoped bridge APIs, no generic Issue writes."""
from pathlib import Path


def build_tech_dash_js() -> str:
    source = (Path(__file__).parent / 'static' / 'ticket_dashboard.js').read_text()
    return '<script>' + source + '</script>'
