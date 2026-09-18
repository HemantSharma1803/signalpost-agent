"""Generates short, human-readable explanations of verified company facts
using the Google Gemini API's FREE tier (Google AI Studio) — no credit card,
no cost, ever, within the free rate limits.

Get a free key: https://aistudio.google.com/api-keys

Important: the model is only ever shown facts already pulled from the
official registry. It is instructed to summarize, never to add facts of its
own — this keeps the accuracy/evidence score high and avoids fabricated
values (which would fail the whole submission per the challenge rules).

To respect the free tier's rate limit (~15 requests/minute), summaries are
generated in BATCHES — many companies per call — instead of one call per
company. This keeps a 1,000-company run well within both the free tier's
limits and the challenge's 45-minute cap.
"""
import json
import time
import requests

from . import config
from .models import CompanyProfile
from .budget_guard import BudgetGuard

SYSTEM_INSTRUCTION = (
    "You summarize verified Norwegian company registry data in 1-2 plain "
    "sentences per company, for a business lookup tool. Only use the facts "
    "given to you. Never invent names, numbers, or financial figures that "
    "are not present in the input. If a field is missing, simply omit it."
)


def _clean_json_text(text: str) -> str:
    """Strip Markdown code fences some models wrap JSON in."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


def _call_gemini(prompt: str) -> str:
    if not config.GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Get a free key at "
            "https://aistudio.google.com/api-keys and add it to your .env file."
        )
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
    }
    response = requests.post(
        config.GEMINI_API_URL,
        params={"key": config.GEMINI_API_KEY},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _facts_for(profile: CompanyProfile) -> dict:
    return {
        "org_number": profile.org_number,
        "name": profile.name,
        "org_form": profile.org_form_description,
        "industry": profile.industry_description,
        "city": profile.city,
        "registration_date": profile.registration_date,
        "founding_date": profile.founding_date,
        "employees": profile.number_of_employees,
        "is_bankrupt": profile.is_bankrupt,
    }


def summarize_company(profile: CompanyProfile, guard: BudgetGuard | None = None) -> str:
    """Single-company summary — used by the CLI/API single-lookup path."""
    prompt = (
        "Write a 1-2 sentence summary of this company using only these "
        f"facts:\n{json.dumps(_facts_for(profile))}"
    )
    text = _call_gemini(prompt)
    if guard:
        guard.record_request(cost_usd=config.ESTIMATED_COST_PER_LLM_CALL_USD)
    return text.strip()


def summarize_batch(
    profiles: list[CompanyProfile], guard: BudgetGuard | None = None
) -> dict:
    """Summarize many companies in ONE request, returning
    {org_number: summary}. Falls back to an empty dict (no summaries, facts
    are untouched) if the batch response can't be parsed — this never
    crashes the run."""
    facts_list = [_facts_for(p) for p in profiles]
    prompt = (
        "Here is a JSON list of verified Norwegian company registry facts. "
        "Return ONLY a JSON object mapping each org_number to a 1-2 sentence "
        "summary using only the given facts for that company. Do not add "
        "any company, field, or figure not present in the input. Do not "
        "wrap the output in markdown.\n\n" + json.dumps(facts_list)
    )
    try:
        text = _call_gemini(prompt)
        if guard:
            guard.record_request(cost_usd=config.ESTIMATED_COST_PER_LLM_CALL_USD)
        parsed = json.loads(_clean_json_text(text))
        if isinstance(parsed, dict):
            return parsed
        return {}
    except Exception:
        # Never let a summary-parsing hiccup break fact collection.
        if guard:
            guard.record_request(cost_usd=config.ESTIMATED_COST_PER_LLM_CALL_USD)
        return {}
    finally:
        time.sleep(config.LLM_REQUEST_INTERVAL_SECONDS)
