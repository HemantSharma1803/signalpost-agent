"""Client for the official Norwegian Accounts Register."""
import time
import requests
from .budget_guard import BudgetGuard

BASE_URL = "https://data.brreg.no/regnskapsregisteret/regnskap"
HEADERS = {"Accept": "application/json", "User-Agent": "signalpost-agent/2.0"}

EMPTY = {"financial_year_from":None,"financial_year_to":None,"revenue":None,
"operating_result":None,"net_result":None,"total_assets":None,"equity":None,
"currency":None,"financial_source_url":None}

def _get(org_number, guard=None, attempts=2):
    url=f"{BASE_URL}/{org_number}"
    last=None
    for attempt in range(attempts):
        if guard: guard.reserve_request(0.0)
        try:
            r=requests.get(url,headers=HEADERS,timeout=15)
            if r.status_code==404: return None
            r.raise_for_status(); return r.json()
        except requests.RequestException as exc:
            last=exc
            if attempt+1<attempts: time.sleep(1+attempt)
    raise last

def _num(value):
    try: return float(value) if value is not None else None
    except (TypeError,ValueError): return None

def get_financials(org_number, guard=None):
    try:
        data=_get(str(org_number),guard=guard)
        if not data: return dict(EMPTY)
        record=data[0] if isinstance(data,list) and data else data
        if not isinstance(record,dict): return dict(EMPTY)
        period=record.get("regnskapsperiode") or {}
        result=record.get("resultatregnskapResultat") or {}
        operating=result.get("driftsresultat") or {}
        income=operating.get("driftsinntekter") or {}
        assets=record.get("eiendeler") or {}
        debt=record.get("egenkapitalGjeld") or {}
        equity=debt.get("egenkapital") or {}
        return {"financial_year_from":period.get("fraDato"),
                "financial_year_to":period.get("tilDato"),
                "revenue":_num(income.get("sumDriftsinntekter")),
                "operating_result":_num(operating.get("driftsresultat")),
                "net_result":_num(result.get("aarsresultat")),
                "total_assets":_num(assets.get("sumEiendeler")),
                "equity":_num(equity.get("sumEgenkapital")),
                "currency":record.get("valuta"),
                "financial_source_url":f"{BASE_URL}/{org_number}"}
    except Exception:
        return dict(EMPTY)
