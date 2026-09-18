"""Client for the Regnskapsregisteret (Norwegian Accounts Register) — a
second official, free Brønnøysund data source, alongside the main
Enhetsregisteret registry. It publishes each company's most recently filed
annual financial figures as open data.

Endpoint: https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}

Not every company has filed accounts (e.g. sole proprietorships often
don't), so a 404 here is normal and expected — it just means no financial
facts are added for that company, nothing else changes.

This client is deliberately defensive: every field is read with .get()
chains so that if a company's response is missing a section, or the API's
JSON shape varies slightly between record types, we simply leave that
figure blank instead of raising an error. Facts are only ever taken
directly from the response — nothing is estimated or invented.
"""
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .budget_guard import BudgetGuard

BASE_URL = "https://data.brreg.no/regnskapsregisteret/regnskap"
HEADERS = {"Accept": "application/json", "User-Agent": "signalpost-agent/1.0"}


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def _get(org_number: str):
    url = f"{BASE_URL}/{org_number}"
    response = requests.get(url, headers=HEADERS, timeout=15)
    if response.status_code == 404:
        return None  # company has no filed accounts — not an error
    response.raise_for_status()
    return response.json()


def _num(value) -> float | None:
    """Safely coerce a value to float, returning None on anything unexpected."""
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def get_financials(org_number: str, guard: BudgetGuard | None = None) -> dict:
    """Returns a dict of financial fields (all None if unavailable). Never
    raises — a missing or malformed response just means fewer facts."""
    empty = {
        "financial_year_from": None,
        "financial_year_to": None,
        "revenue": None,
        "operating_result": None,
        "net_result": None,
        "total_assets": None,
        "equity": None,
        "currency": None,
        "financial_source_url": None,
    }
    try:
        data = _get(org_number)
        if guard:
            guard.record_request(cost_usd=0.0)  # this registry is also free
        if not data:
            return empty

        # The API can return either a single object or a list of yearly
        # filings (most recent first) depending on the record type.
        record = data[0] if isinstance(data, list) and data else data
        if not isinstance(record, dict):
            return empty

        period = record.get("regnskapsperiode") or {}
        result_accounts = record.get("resultatregnskapResultat") or {}
        driftsresultat = result_accounts.get("driftsresultat") or {}
        driftsinntekter = driftsresultat.get("driftsinntekter") or {}
        eiendeler = record.get("eiendeler") or {}
        egenkapital_gjeld = record.get("egenkapitalGjeld") or {}
        egenkapital = egenkapital_gjeld.get("egenkapital") or {}

        return {
            "financial_year_from": period.get("fraDato"),
            "financial_year_to": period.get("tilDato"),
            "revenue": _num(driftsinntekter.get("sumDriftsinntekter")),
            "operating_result": _num(driftsresultat.get("driftsresultat")),
            "net_result": _num(result_accounts.get("aarsresultat")),
            "total_assets": _num(eiendeler.get("sumEiendeler")),
            "equity": _num(egenkapital.get("sumEgenkapital")),
            "currency": record.get("valuta"),
            "financial_source_url": f"{BASE_URL}/{org_number}",
        }
    except Exception:
        # Financial data is a bonus, never a requirement — any failure here
        # must never break fact collection for the rest of the company.
        return empty
