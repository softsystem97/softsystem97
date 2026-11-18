"""Private, read-only quality audit for the three technician question banks.

Never return question prompts, answers, or answer-key details to callers.
"""

from .rules import validate_question


MAX_ACTIVE_BANK_SIZE = 500


def audit_bank(rows, required, total=None):
    """Count broken and duplicate active questions without exposing their contents.

    ``rows`` are Frappe dict records loaded by a System Manager-only method.
    A bank over the exam selector's 500-question limit cannot be launched.
    """
    if total is None:
        total = len(rows)
    if not isinstance(total, int) or total < 0 or total < len(rows):
        raise ValueError("Taille de banque incohérente.")
    invalid = 0
    duplicates = 0
    seen_prompts = set()
    for row in rows:
        prompt = row.get("prompt")
        try:
            validate_question(prompt, row.get("options_json"),
                              row.get("correct_option"), row.get("category") or "")
        except (ValueError, TypeError):
            invalid += 1
        if isinstance(prompt, str):
            normalized = " ".join(prompt.casefold().split())
            if normalized in seen_prompts:
                duplicates += 1
            seen_prompts.add(normalized)
    complete = total <= MAX_ACTIVE_BANK_SIZE and total == len(rows)
    return {"active_count": total, "invalid_count": invalid,
            "duplicate_count": duplicates,
            "ready": complete and total >= required and invalid == 0 and duplicates == 0}
