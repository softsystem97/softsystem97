"""Bounded cyber finance scenarios and declaration-only compliance guidance."""
from decimal import Decimal, InvalidOperation
from softsystem97.cyber_assessment.catalog import QUESTIONS, validate_answers
from softsystem97.cyber_assessment.recommendations import roadmap

NIST_FUNCTION={"inventory":"Identify","mfa":"Protect","backup":"Recover",
"updates":"Protect","endpoint":"Protect","access":"Protect","network":"Protect",
"training":"Protect","incident":"Respond","suppliers":"Govern"}

def amount(value, maximum):
    if isinstance(value,bool) or not isinstance(value,(str,int,Decimal)):
        raise ValueError("Montant invalide.")
    try: result=Decimal(str(value))
    except InvalidOperation as exc: raise ValueError("Montant invalide.") from exc
    if not result.is_finite() or result<0 or result>Decimal(maximum) or result.as_tuple().exponent<-2:
        raise ValueError("Montant hors limites.")
    return result

def disruption_estimate(hours, hourly_impact_eur, recovery_cost_eur):
    duration=amount(hours,"720")
    rate=amount(hourly_impact_eur,"1000000")
    costs=amount(recovery_cost_eur,"100000000")
    return {"total_eur":format((duration*rate+costs).quantize(Decimal("0.01")),".2f"),
      "warning":"Estimation purement hypothétique, ni perte certaine ni devis."}

def advisory(answers):
    checked=validate_answers(answers)
    return {"controls":[{"label":QUESTIONS[key],"function":NIST_FUNCTION[key],
      "answer":checked[key],"verified":False} for key in QUESTIONS],
      "roadmap":roadmap(checked),
      "warning":"Données déclaratives. Aucune conformité NIST, NIS2, RGPD ou DORA certifiée."}
