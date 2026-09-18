"""Orchestrates the full pipeline: registry lookup -> financial lookup ->
verification -> LLM summary -> save, while respecting the budget guard at
every step.

Two run modes:
- process_bulk(): builds a fresh dataset of `target_count` companies.
- process_update(): re-fetches every company already in the saved dataset,
  so facts stay current and any changes are tracked (see CompanyProfile's
  first_seen / last_updated / changed_fields).

Bulk mode summarizes companies in BATCHES (not one LLM call each) to stay
comfortably within Google Gemini's free-tier rate limit and the challenge's
45-minute cap.
"""
import json
import logging
import os
from datetime import datetime, timezone
from tqdm import tqdm

from . import config, brreg_client, regnskap_client, llm_client
from .budget_guard import BudgetGuard, BudgetExceeded
from .models import CompanyProfile

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger("signalpost-agent")

TRACKED_FIELDS = [
    "name", "org_form_description", "industry_description", "address",
    "postal_code", "city", "number_of_employees", "is_bankrupt", "homepage",
    "revenue", "operating_result", "net_result", "equity",
]


def _fetch_full_profile(org_number: str, guard: BudgetGuard) -> CompanyProfile:
    """Registry facts + financial facts for one company (no LLM here)."""
    profile = brreg_client.get_company(org_number, guard=guard)
    financials = regnskap_client.get_financials(org_number, guard=guard)
    for k, v in financials.items():
        setattr(profile, k, v)
    return profile


def process_one(org_number: str, guard: BudgetGuard, use_llm: bool = True) -> CompanyProfile:
    """Look up one company and return a verified, sourced, dated profile."""
    profile = _fetch_full_profile(org_number, guard)
    if use_llm:
        try:
            profile.summary = llm_client.summarize_company(profile, guard=guard)
        except Exception as exc:  # noqa: BLE001 - never let a summary failure kill the run
            log.warning("LLM summary skipped for %s: %s", org_number, exc)
            profile.summary = None
    return profile


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _summarize_all(profiles: list[CompanyProfile], guard: BudgetGuard) -> None:
    if not profiles:
        return
    log.info(
        "Generating summaries in batches of %d (free-tier friendly)...",
        config.LLM_BATCH_SIZE,
    )
    try:
        for batch in tqdm(
            list(_chunks(profiles, config.LLM_BATCH_SIZE)), desc="Summarizing batches"
        ):
            summaries = llm_client.summarize_batch(batch, guard=guard)
            for p in batch:
                p.summary = summaries.get(p.org_number)
    except BudgetExceeded as exc:
        log.warning("Stopping early during summarization — %s", exc)


def process_bulk(target_count: int = 1000, use_llm: bool = True) -> list[dict]:
    """Build the full company_profiles.json dataset required for submission,
    stopping safely if the runtime/request/cost budget is reached first."""
    guard = BudgetGuard(
        max_seconds=config.BULK_MAX_RUNTIME_SECONDS,
        max_requests=config.BULK_MAX_OUTBOUND_REQUESTS,
        max_cost_usd=config.BULK_MAX_COST_USD,
    )
    profiles: list[CompanyProfile] = []
    now = datetime.now(timezone.utc).isoformat()

    log.info("Fetching list of %d organization numbers from the registry...", target_count)
    org_numbers = brreg_client.list_org_numbers(target_count, guard=guard)
    log.info("Got %d organization numbers. Fetching verified facts...", len(org_numbers))

    try:
        for org_number in tqdm(org_numbers, desc="Fetching registry + financial facts"):
            try:
                profile = _fetch_full_profile(org_number, guard)
                profile.first_seen = now
                profile.last_updated = now
                profiles.append(profile)
            except brreg_client.CompanyNotFound:
                continue
            except AssertionError as exc:
                log.warning("Skipped mismatched record: %s", exc)
                continue
    except BudgetExceeded as exc:
        log.warning("Stopping early during fact collection — %s", exc)

    if use_llm:
        _summarize_all(profiles, guard)

    results = [p.to_dict() for p in profiles]
    _save(results)
    log.info("Done. %s", guard.summary())
    return results


def process_update(use_llm: bool = True) -> list[dict]:
    """Re-fetch every company already in output/company_profiles.json so the
    dataset stays current, tracking what changed since the last run. This
    is what keeps daily-tested profiles accurate rather than stale."""
    if not os.path.exists(config.OUTPUT_FILE):
        log.error(
            "No existing dataset found at %s — run --bulk first.", config.OUTPUT_FILE
        )
        return []

    with open(config.OUTPUT_FILE, "r", encoding="utf-8") as f:
        existing = {row["org_number"]: row for row in json.load(f)}

    guard = BudgetGuard(
        max_seconds=config.BULK_MAX_RUNTIME_SECONDS,
        max_requests=config.BULK_MAX_OUTBOUND_REQUESTS,
        max_cost_usd=config.BULK_MAX_COST_USD,
    )
    now = datetime.now(timezone.utc).isoformat()
    profiles: list[CompanyProfile] = []
    changed_count = 0

    try:
        for org_number, old_row in tqdm(existing.items(), desc="Refreshing profiles"):
            try:
                profile = _fetch_full_profile(org_number, guard)
            except brreg_client.CompanyNotFound:
                continue
            except AssertionError as exc:
                log.warning("Skipped mismatched record: %s", exc)
                continue

            profile.first_seen = old_row.get("first_seen", old_row.get("fetched_at", now))
            profile.last_updated = now
            changed = [
                field
                for field in TRACKED_FIELDS
                if str(old_row.get(field)) != str(getattr(profile, field))
            ]
            profile.changed_fields = changed
            if changed:
                changed_count += 1
            # Preserve the previous summary; it's only regenerated below if
            # something factual actually changed, saving LLM calls.
            profile.summary = old_row.get("summary") if not changed else None
            profiles.append(profile)
    except BudgetExceeded as exc:
        log.warning("Stopping early during refresh — %s", exc)

    if use_llm:
        needs_summary = [p for p in profiles if p.summary is None]
        _summarize_all(needs_summary, guard)

    results = [p.to_dict() for p in profiles]
    _save(results)
    log.info(
        "Update complete: %d profiles refreshed, %d had real changes. %s",
        len(results), changed_count, guard.summary(),
    )
    return results


def _save(results: list[dict]) -> None:
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    with open(config.OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log.info("Saved %d profiles to %s", len(results), config.OUTPUT_FILE)
