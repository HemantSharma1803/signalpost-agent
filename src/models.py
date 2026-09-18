"""Data model for a single company profile produced by the agent."""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class CompanyProfile:
    org_number: str
    name: str
    org_form_code: Optional[str] = None
    org_form_description: Optional[str] = None
    industry_code: Optional[str] = None
    industry_description: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    municipality: Optional[str] = None
    registration_date: Optional[str] = None
    founding_date: Optional[str] = None
    number_of_employees: Optional[int] = None
    is_bankrupt: Optional[bool] = None
    homepage: Optional[str] = None

    # Financial facts (from the official Regnskapsregisteret accounts
    # register) — only populated when the company has filed accounts and
    # the figures could be parsed. Never estimated or invented.
    financial_year_from: Optional[str] = None
    financial_year_to: Optional[str] = None
    revenue: Optional[float] = None
    operating_result: Optional[float] = None
    net_result: Optional[float] = None
    total_assets: Optional[float] = None
    equity: Optional[float] = None
    currency: Optional[str] = None
    financial_source_url: Optional[str] = None

    # Provenance — required so every fact can be traced and matched
    # back to the correct company.
    source_url: str = ""
    fetched_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # Tracking for the "keep profiles current" requirement.
    first_seen: Optional[str] = None
    last_updated: Optional[str] = None
    changed_fields: list = field(default_factory=list)

    # LLM-generated, human-readable explanation of the verified facts above.
    summary: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
