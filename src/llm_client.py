"""Gemini summary layer. It only summarizes facts already retrieved."""
import json, time, requests
from . import config
from .budget_guard import BudgetGuard

SYSTEM_INSTRUCTION = (
    "Summarize verified Norwegian company registry facts. Use ONLY the supplied "
    "facts. Never invent facts, people, financial values, URLs, or dates. "
    "Return concise 1-2 sentence summaries."
)

def _clean_json(text):
    text=text.strip()
    if text.startswith("```"):
        text=text[3:]
        if text.lower().startswith("json"): text=text[4:]
        if text.endswith("```"): text=text[:-3]
    return text.strip()

def _call_gemini(prompt, guard):
    if not config.GEMINI_API_KEY:
        return None
    payload={"system_instruction":{"parts":[{"text":SYSTEM_INSTRUCTION}]},
             "contents":[{"parts":[{"text":prompt}]}],
             "generationConfig":{"maxOutputTokens":2048}}
    for attempt in range(3):
        guard.reserve_request(config.ESTIMATED_COST_PER_LLM_CALL_USD)
        try:
            r=requests.post(config.GEMINI_API_URL,params={"key":config.GEMINI_API_KEY},
                            json=payload,timeout=45)
            if r.status_code==429 or r.status_code>=500:
                if attempt<2:
                    time.sleep(min(2**attempt,4)); continue
            r.raise_for_status()
            data=r.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
            if attempt<2:
                time.sleep(min(2**attempt,4)); continue
            return None
    return None

def _facts(profile):
    return {k:getattr(profile,k) for k in (
        "org_number","name","org_form_description","industry_description",
        "city","registration_date","founding_date","number_of_employees",
        "is_bankrupt","revenue","operating_result","net_result","total_assets",
        "equity","currency")}

def summarize_company(profile, guard):
    text=_call_gemini(
        "Write a concise summary from these verified facts:\n"+
        json.dumps(_facts(profile),ensure_ascii=False), guard)
    return text.strip() if text else None

def summarize_batch(profiles, guard):
    if not profiles or not config.GEMINI_API_KEY: return {}
    facts=[_facts(p) for p in profiles]
    prompt=("Return ONLY a JSON object mapping each org_number to a 1-2 sentence "
            "summary. Use only the corresponding facts.\n"+
            json.dumps(facts,ensure_ascii=False))
    text=_call_gemini(prompt,guard)
    if not text: return {}
    try:
        parsed=json.loads(_clean_json(text))
        return parsed if isinstance(parsed,dict) else {}
    except (json.JSONDecodeError,TypeError):
        return {}
    finally:
        time.sleep(config.LLM_REQUEST_INTERVAL_SECONDS)
