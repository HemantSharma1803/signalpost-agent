"""Client for the official Brønnøysund Register Centre APIs."""
import time
import requests
from . import config
from .models import CompanyProfile
from .budget_guard import BudgetGuard

HEADERS = {"Accept": "application/json", "User-Agent": "signalpost-agent/2.0"}
class CompanyNotFound(Exception): pass

def _get(url, params=None, guard=None, attempts=3):
    last = None
    for attempt in range(attempts):
        if guard: guard.reserve_request(0.0)
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=15)
            if r.status_code == 404: raise CompanyNotFound(url)
            r.raise_for_status()
            return r.json()
        except CompanyNotFound: raise
        except (requests.RequestException, ValueError) as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(min(2 ** attempt, 4))
    raise last

def _parse_entity(entity):
    org_number = str(entity.get("organisasjonsnummer", ""))
    address_info = entity.get("forretningsadresse") or {}
    org_form = entity.get("organisasjonsform") or {}
    industry = entity.get("naeringskode1") or {}
    return CompanyProfile(
        org_number=org_number, name=entity.get("navn", ""),
        org_form_code=org_form.get("kode"),
        org_form_description=org_form.get("beskrivelse"),
        industry_code=industry.get("kode"),
        industry_description=industry.get("beskrivelse"),
        address=", ".join(address_info.get("adresse", []) or []) or None,
        postal_code=address_info.get("postnummer"), city=address_info.get("poststed"),
        municipality=address_info.get("kommune"),
        registration_date=entity.get("registreringsdatoEnhetsregisteret"),
        founding_date=entity.get("stiftelsesdato"),
        number_of_employees=entity.get("antallAnsatte"),
        is_bankrupt=entity.get("konkurs"), homepage=entity.get("hjemmeside"),
        source_url=f"https://data.brreg.no/enhetsregisteret/api/enheter/{org_number}",
    )

def get_company(org_number, guard=None):
    org_number = str(org_number).strip()
    if not org_number.isdigit():
        raise ValueError("Norwegian organization number must contain digits only.")
    entity = _get(config.BRREG_ENTITY_ENDPOINT.format(org_number=org_number), guard=guard)
    profile = _parse_entity(entity)
    if profile.org_number != org_number:
        raise ValueError("Org number mismatch — record discarded.")
    return profile

def list_entities(target_count, guard=None, page_size=None):
    """Return registry entities directly. This avoids 1,000 redundant detail calls."""
    target_count = max(0, int(target_count))
    page_size = page_size or config.BRREG_PAGE_SIZE
    entities_out = []
    page = 0
    while len(entities_out) < target_count:
        data = _get(config.BRREG_LIST_ENDPOINT,
                    params={"page": page, "size": min(page_size, target_count-len(entities_out))},
                    guard=guard)
        entities = data.get("_embedded", {}).get("enheter", [])
        if not entities: break
        for e in entities:
            if e.get("organisasjonsnummer"):
                entities_out.append(e)
                if len(entities_out) >= target_count: break
        page += 1
    return entities_out[:target_count]

def list_org_numbers(target_count, guard=None):
    return [str(e.get("organisasjonsnummer")) for e in list_entities(target_count, guard=guard)]
