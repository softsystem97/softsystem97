"""Pure aggregation of already authorized Cyber N4 mission states."""

def summarize(missions):
    """Counts only confirmed, currently authorized missions."""
    return {
        "total": len(missions),
        "offered": sum(m["state"] == "OFFERED" for m in missions),
        "in_progress": sum(m["state"] in ("ACCEPTED", "IN_PROGRESS") for m in missions),
        "reports": sum(m["state"] == "REPORT_SUBMITTED" for m in missions),
        "closed": sum(m["state"] == "CLIENT_ACCEPTED" for m in missions),
        "disputed": sum(m["state"] in ("DISPUTED", "REWORK_PENDING_APPROVAL") for m in missions),
    }


