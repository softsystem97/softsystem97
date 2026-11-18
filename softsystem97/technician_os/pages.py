"""Server-side page admission: URLs are no substitute for track authorization."""

import frappe

from .api import _enabled, _manager, _my_active_profile
from .rules import TRACKS, track_settings


def technician_page(context, track):
    _enabled()
    track_settings(track)
    profile = _my_active_profile()
    if profile.track != track:
        frappe.throw("Cet espace appartient à une autre spécialité.", frappe.PermissionError)
    context.no_cache = 1
    context.tech_track = track
    context.title = f"SS97 TECH OS — {TRACKS[track]['label']}"


def admin_page(context):
    _enabled()
    _manager()
    context.no_cache = 1
    context.title = "SS97 TECH OS — Administration"
