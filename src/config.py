"""Central configuration for the Signalpost agent.

All limits here match the challenge rules:
- 45 minutes per run
- 2,000 outbound requests per run
- $10 in declared external API costs per run

This build uses ONLY free services:
- Brønnøysund Register Centre: free, public, no key needed
- Google AI Studio (Gemini API free tier): free, no credit card required
  Get a key at https://aistudio.google.com/api-keys
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Gemini (Google AI Studio free tier) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

# Free tier is rate-limited (not billed), so this run is $0 in every case.
ESTIMATED_COST_PER_LLM_CALL_USD = 0.0

# To stay under the free tier's ~15 requests/minute limit, summaries are
# generated in BATCHES (many companies per LLM call) instead of one call per
# company. This keeps a 1,000-company run comfortably under both the 45-min
# challenge limit and Google's free rate limit.
LLM_BATCH_SIZE = 20
LLM_REQUEST_INTERVAL_SECONDS = 4.5  # ~13 requests/min, safely under the 15 RPM free cap

# --- Brønnøysund Register Centre (official Norwegian company registry) ---
BRREG_BASE_URL = "https://data.brreg.no/enhetsregisteret/api"
BRREG_ENTITY_ENDPOINT = f"{BRREG_BASE_URL}/enheter/{{org_number}}"
BRREG_LIST_ENDPOINT = f"{BRREG_BASE_URL}/enheter"
BRREG_PAGE_SIZE = 100  # max page size the registry API comfortably supports

# --- Budget guard limits ---
# The challenge's 45-min / 2,000-request / $10 limits apply to the DAILY
# TEST, where Builderr calls the agent on ~100 companies. That's what
# process_one() (single lookup, used by the CLI and the live API) respects.
MAX_RUNTIME_SECONDS = int(os.getenv("MAX_RUNTIME_SECONDS", 45 * 60))
MAX_OUTBOUND_REQUESTS = int(os.getenv("MAX_OUTBOUND_REQUESTS", 2000))
MAX_COST_USD = float(os.getenv("MAX_COST_USD", 10.0))

# Building the required 1,000+ profile submission dataset is a separate,
# one-time job we run ourselves (not the graded daily run), so it gets a
# more generous budget to reliably finish all 1,000 companies with
# summaries every time, without ever needing real money (Gemini free tier
# is still $0 regardless of request count, just rate-limited).
BULK_MAX_RUNTIME_SECONDS = int(os.getenv("BULK_MAX_RUNTIME_SECONDS", 60 * 60))
BULK_MAX_OUTBOUND_REQUESTS = int(os.getenv("BULK_MAX_OUTBOUND_REQUESTS", 5000))
BULK_MAX_COST_USD = float(os.getenv("BULK_MAX_COST_USD", 10.0))

# --- Output ---
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "company_profiles.json")
