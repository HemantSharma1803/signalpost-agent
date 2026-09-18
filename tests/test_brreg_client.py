"""Unit test for entity parsing — does not hit the network."""
from src.brreg_client import _parse_entity

SAMPLE_ENTITY = {
    "organisasjonsnummer": "923609016",
    "navn": "EXAMPLE COMPANY AS",
    "organisasjonsform": {"kode": "AS", "beskrivelse": "Aksjeselskap"},
    "naeringskode1": {"kode": "62.010", "beskrivelse": "Programmering"},
    "forretningsadresse": {
        "adresse": ["Eksempelgata 1"],
        "postnummer": "0123",
        "poststed": "OSLO",
        "kommune": "OSLO",
    },
    "registreringsdatoEnhetsregisteret": "2015-06-01",
    "stiftelsesdato": "2015-05-15",
    "antallAnsatte": 10,
    "konkurs": False,
    "hjemmeside": "example.no",
}


def test_parse_entity_maps_all_fields():
    profile = _parse_entity(SAMPLE_ENTITY)
    assert profile.org_number == "923609016"
    assert profile.name == "EXAMPLE COMPANY AS"
    assert profile.org_form_description == "Aksjeselskap"
    assert profile.industry_description == "Programmering"
    assert profile.city == "OSLO"
    assert profile.number_of_employees == 10
    assert profile.is_bankrupt is False
    assert profile.source_url.endswith("923609016")


def test_parse_entity_handles_missing_optional_fields():
    minimal = {"organisasjonsnummer": "111111111", "navn": "MINIMAL AS"}
    profile = _parse_entity(minimal)
    assert profile.org_number == "111111111"
    assert profile.address is None
    assert profile.number_of_employees is None
