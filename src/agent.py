"""Signalpost orchestration.

Bulk mode is deliberately request-efficient:
- With no input list, the official registry list endpoint provides core facts
  for 1,000 companies in about 10 requests, then accounts are checked once per
  company.
- With company_numbers.txt, the agent processes exactly those organisation
  numbers. That path makes two registry requests per company and therefore
  intentionally does not call Gemini during the same bulk run.
- Summaries have a deterministic local fallback, so missing Gemini access never
  prevents a complete profile from being written.
"""
import json, logging, os
from datetime import datetime, timezone
from tqdm import tqdm
from . import config, brreg_client, regnskap_client, llm_client
from .budget_guard import BudgetGuard, BudgetExceeded
from .models import CompanyProfile

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log=logging.getLogger("signalpost-agent")

TRACKED_FIELDS=[
    "name","org_form_description","industry_description","address","postal_code",
    "city","number_of_employees","is_bankrupt","homepage","revenue",
    "operating_result","net_result","equity","total_assets",
]

def _local_summary(p):
    bits=[]
    if p.name: bits.append(p.name)
    if p.industry_description: bits.append(f"operates in {p.industry_description}")
    if p.city: bits.append(f"based in {p.city}")
    if p.number_of_employees is not None: bits.append(f"{p.number_of_employees} employees")
    if p.founding_date: bits.append(f"founded {p.founding_date}")
    return ". ".join(bits) + "." if bits else "No additional verified description is available."

def _sources(p):
    now=p.fetched_at
    sources=[{"type":"company_registry","url":p.source_url,"retrieved_at":now}]
    if p.financial_source_url:
        sources.append({"type":"accounts_register","url":p.financial_source_url,
                        "retrieved_at":now,
                        "reporting_period":{"from":p.financial_year_from,"to":p.financial_year_to}})
    return sources

def _attach_financials(p, guard):
    for k,v in regnskap_client.get_financials(p.org_number,guard=guard).items():
        setattr(p,k,v)
    p.sources=_sources(p)
    return p

def _fetch_full_profile(org_number, guard):
    p=brreg_client.get_company(org_number,guard=guard)
    return _attach_financials(p,guard)

def process_one(org_number, guard, use_llm=True):
    p=_fetch_full_profile(org_number,guard)
    p.summary=llm_client.summarize_company(p,guard) if use_llm else _local_summary(p)
    if not p.summary: p.summary=_local_summary(p)
    p.sources=_sources(p)
    return p

def _profile_from_entity(entity, guard):
    p=brreg_client._parse_entity(entity)
    return _attach_financials(p,guard)

def _read_org_list(path):
    if not os.path.exists(path): return []
    out=[]
    with open(path,encoding="utf-8") as f:
        for line in f:
            value=line.strip().replace(",","")
            if value.isdigit() and len(value)>=6:
                out.append(value)
    return list(dict.fromkeys(out))

def _save(results):
    os.makedirs(config.OUTPUT_DIR,exist_ok=True)
    tmp=config.OUTPUT_FILE+".tmp"
    with open(tmp,"w",encoding="utf-8") as f:
        json.dump(results,f,ensure_ascii=False,indent=2)
    os.replace(tmp,config.OUTPUT_FILE)
    log.info("Saved %d profiles to %s",len(results),config.OUTPUT_FILE)

def process_bulk(target_count=1000,use_llm=False,org_list_path=None):
    guard=BudgetGuard(config.BULK_MAX_RUNTIME_SECONDS,
                      config.BULK_MAX_OUTBOUND_REQUESTS,
                      config.BULK_MAX_COST_USD)
    target_count=max(1,int(target_count))
    now=datetime.now(timezone.utc).isoformat()
    profiles=[]
    supplied=_read_org_list(org_list_path or config.ORG_LIST_FILE)

    try:
        if supplied:
            orgs=supplied[:target_count]
            log.info("Using %d organisation numbers from %s",len(orgs),org_list_path or config.ORG_LIST_FILE)
            for org in tqdm(orgs,desc="Fetching selected companies"):
                try:
                    p=_fetch_full_profile(org,guard)
                    p.first_seen=now; p.last_updated=now; p.summary=_local_summary(p)
                    profiles.append(p)
                except (brreg_client.CompanyNotFound, ValueError) as exc:
                    log.warning("Skipping %s: %s",org,exc)
        else:
            log.info("No company_numbers.txt found; using official registry listing.")
            entities=brreg_client.list_entities(target_count,guard=guard)
            for entity in tqdm(entities,desc="Fetching accounts for companies"):
                try:
                    p=_profile_from_entity(entity,guard)
                    p.first_seen=now; p.last_updated=now; p.summary=_local_summary(p)
                    profiles.append(p)
                except (ValueError, TypeError) as exc:
                    log.warning("Skipping malformed registry record: %s",exc)
    except BudgetExceeded as exc:
        log.warning("Stopped safely at budget boundary: %s",exc)

    # Optional Gemini enrichment only when there is sufficient request headroom.
    if use_llm and profiles:
        remaining=guard.max_requests-guard.request_count
        batches=(len(profiles)+config.LLM_BATCH_SIZE-1)//config.LLM_BATCH_SIZE
        if batches <= remaining:
            try:
                for batch in tqdm([profiles[i:i+config.LLM_BATCH_SIZE]
                                   for i in range(0,len(profiles),config.LLM_BATCH_SIZE)],
                                  desc="Generating Gemini summaries"):
                    summaries=llm_client.summarize_batch(batch,guard)
                    for p in batch:
                        if summaries.get(p.org_number): p.summary=summaries[p.org_number]
            except BudgetExceeded as exc:
                log.warning("Gemini summary phase stopped safely: %s",exc)
        else:
            log.info("Skipping Gemini in bulk mode: %d requests remain, %d needed.",remaining,batches)

    results=[p.to_dict() for p in profiles]
    _save(results)
    log.info("Bulk complete: %d/%d profiles. %s",len(results),target_count,guard.summary())
    return results

def process_update(use_llm=False):
    if not os.path.exists(config.OUTPUT_FILE):
        log.error("No dataset at %s. Run --bulk first.",config.OUTPUT_FILE); return []
    with open(config.OUTPUT_FILE,encoding="utf-8") as f:
        existing={row["org_number"]:row for row in json.load(f)}
    guard=BudgetGuard(config.BULK_MAX_RUNTIME_SECONDS,
                      config.BULK_MAX_OUTBOUND_REQUESTS,
                      config.BULK_MAX_COST_USD)
    now=datetime.now(timezone.utc).isoformat(); profiles=[]
    try:
        for org,old in tqdm(existing.items(),desc="Refreshing profiles"):
            try:
                p=_fetch_full_profile(org,guard)
            except (brreg_client.CompanyNotFound,ValueError): continue
            p.first_seen=old.get("first_seen",old.get("fetched_at",now)); p.last_updated=now
            p.changed_fields=[f for f in TRACKED_FIELDS if str(old.get(f))!=str(getattr(p,f))]
            p.summary=old.get("summary") if not p.changed_fields else _local_summary(p)
            p.sources=_sources(p); profiles.append(p)
    except BudgetExceeded as exc:
        log.warning("Refresh stopped safely: %s",exc)
    results=[p.to_dict() for p in profiles]; _save(results); return results
