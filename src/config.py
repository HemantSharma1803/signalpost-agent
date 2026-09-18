"""Central configuration for the Signalpost agent."""
import os
from dotenv import load_dotenv

load_dotenv()

# Gemini 2.0 Flash was shut down on 2026-06-01. Use a current stable model.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)
ESTIMATED_COST_PER_LLM_CALL_USD = 0.0
LLM_BATCH_SIZE = int(os.getenv("LLM_BATCH_SIZE", "20"))
LLM_REQUEST_INTERVAL_SECONDS = float(os.getenv("LLM_REQUEST_INTERVAL_SECONDS", "1.0"))

BRREG_BASE_URL = "https://data.brreg.no/enhetsregisteret/api"
BRREG_ENTITY_ENDPOINT = f"{BRREG_BASE_URL}/enheter/{{org_number}}"
BRREG_LIST_ENDPOINT = f"{BRREG_BASE_URL}/enheter"
BRREG_PAGE_SIZE = int(os.getenv("BRREG_PAGE_SIZE", "100"))

MAX_RUNTIME_SECONDS = int(os.getenv("MAX_RUNTIME_SECONDS", "2700"))
MAX_OUTBOUND_REQUESTS = int(os.getenv("MAX_OUTBOUND_REQUESTS", "2000"))
MAX_COST_USD = float(os.getenv("MAX_COST_USD", "10.0"))

BULK_MAX_RUNTIME_SECONDS = int(os.getenv("BULK_MAX_RUNTIME_SECONDS", "2700"))
BULK_MAX_OUTBOUND_REQUESTS = int(os.getenv("BULK_MAX_OUTBOUND_REQUESTS", "2000"))
BULK_MAX_COST_USD = float(os.getenv("BULK_MAX_COST_USD", "10.0"))

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "company_profiles.json")
ORG_LIST_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "company_numbers.txt")
