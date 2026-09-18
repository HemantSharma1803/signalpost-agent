"""Client for the Brønnøysund Register Centre's public Enhetsregisteret API.

This is Norway's official, free, government company registry — the
"permitted public source" this agent relies on as its primary, authoritative
source of truth. No API key is required.

Docs: https://data.brreg.no/enhetsregisteret/api/docs/index.html
"""
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from . import config
from .models import CompanyProfile
from .budget_guard import BudgetGuard

HEADERS = {"Accept": "application/json", "User-Agent": "signalpost-agent/1.0"}


class CompanyNotFound(Exception):
    pass


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def _get(url: str, params: dict | None = None) -> dict:
    response = requests.get(url, headers=HEADERS, params=params, timeout=15)
    if response.status_code == 404:
        raise CompanyNotFound(url)
    response.raise_for_status()
    return response.json()


def _parse_entity(entity: dict) -> CompanyProfile:
    org_number = entity.get("organisasjonsnummer", "")
    address_info = entity.get("forretningsadresse") or {}
    org_form = entity.get("organisasjonsform") or {}
    industry = entity.get("naeringskode1") or {}

    return CompanyProfile(
        org_number=org_number,
        name=entity.get("navn", ""),
        org_form_code=org_form.get("kode"),
        org_form_description=org_form.get("beskrivelse"),
        industry_code=industry.get("kode"),
        industry_description=industry.get("beskrivelse"),
        address=", ".join(address_info.get("adresse", []) or []) or None,
        postal_code=address_info.get("postnummer"),
        city=address_info.get("poststed"),
        municipality=address_info.get("kommune"),
        registration_date=entity.get("registreringsdatoEnhetsregisteret"),
        founding_date=entity.get("stiftelsesdato"),
        number_of_employees=entity.get("antallAnsatte"),
        is_bankrupt=entity.get("konkurs"),
        homepage=entity.get("hjemmeside"),
        source_url=f"https://data.brreg.no/enhetsregisteret/api/enheter/{org_number}",
    )


def get_company(org_number: str, guard: BudgetGuard | None = None) -> CompanyProfile:
    """Fetch a single company's verified facts by organization number."""
    url = config.BRREG_ENTITY_ENDPOINT.format(org_number=org_number)
    entity = _get(url)
    if guard:
        guard.record_request(cost_usd=0.0)  # the registry API is free
    profile = _parse_entity(entity)
    # Safety check: never let a fact get attached to the wrong company.
    assert profile.org_number == org_number, "Org number mismatch — discarding record."
    return profile


def list_org_numbers(target_count: int, guard: BudgetGuard | None = None) -> list[str]:
    """Pull a list of real, currently-registered Norwegian org numbers by
    paging through the public registry listing endpoint."""
    org_numbers: list[str] = []
    page = 0
    while len(org_numbers) < target_count:
        params = {"page": page, "size": config.BRREG_PAGE_SIZE}
        data = _get(config.BRREG_LIST_ENDPOINT, params=params)
        if guard:
            guard.record_request(cost_usd=0.0)
        entities = data.get("_embedded", {}).get("enheter", [])
        if not entities:
            break  # no more pages available
        org_numbers.extend(e.get("organisasjonsnummer") for e in entities)
        page += 1
    return org_numbers[:target_count]
