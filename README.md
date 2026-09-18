# Signalpost Agent — Norwegian Company Information Finder

An agent that takes a **Norwegian organization number** and returns verified
company facts, with source links and dates — built for the
[Signalpost: Build An Agent That Finds Company Information](https://unstop.com/hackathons/signalpost-build-an-agent-that-finds-company-information-builderrai-1754883)
challenge (Unstop / Builderr.ai).

## How it works

1. **Primary source — Brønnøysund Register Centre (official, free, public API)**
   `https://data.brreg.no/enhetsregisteret/api` — Norway's government company
   registry. No API key required. Every fact pulled from here comes with:
   - the exact **source URL** (the registry entry for that org number)
   - the **date fetched**
   - the org number it belongs to (so facts never get attached to the wrong
     company — this is checked before saving)

2. **LLM layer — Google Gemini API, FREE tier** (`gemini-2.0-flash`, via
   Google AI Studio — no credit card required, ever)
   Takes the verified registry facts and writes a short, human-readable
   summary/explanation for each company. The LLM **never invents facts** —
   it only rephrases what the registry already returned, which keeps
   accuracy high and cost at **$0**. Summaries are generated in **batches**
   (many companies per request) so a 1,000-company run stays comfortably
   inside Google's free-tier rate limit and the challenge's 45-minute cap.

3. **Budget guard**
   Tracks elapsed time, number of outbound requests, and estimated USD cost
   in real time, and stops the run safely before exceeding:
   - 45 minutes
   - 2,000 outbound requests
   - $10 in API costs

## Project structure

```
signalpost-agent/
├── main.py                # CLI entry point — the "one command to run it"
├── src/
│   ├── config.py           # limits, model name, constants
│   ├── models.py           # CompanyProfile data model
│   ├── brreg_client.py     # Brønnøysund registry API client
│   ├── llm_client.py       # Gemini (free tier) summary generator
│   ├── budget_guard.py     # time/request/cost tracking + safe stop
│   ├── company_list.py     # pulls a list of org numbers to process
│   └── agent.py            # orchestrates everything
├── api/
│   └── server.py           # FastAPI app for a live demo / deployment
├── tests/
│   └── test_brreg_client.py
├── output/                 # generated company_profiles.json lands here
├── Dockerfile
├── render.yaml             # one-click deploy config for Render.com
├── requirements.txt
└── .env.example
```

## Getting your free Gemini API key

1. Go to https://aistudio.google.com/api-keys
2. Sign in with any Google account (no credit card, no billing setup)
3. Click **Create API key** → copy it

That's it — this key is free permanently within Google's rate limits
(no trial period, no expiry).

## Setup

```bash
git clone <your-repo-url>
cd signalpost-agent
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then paste your FREE Gemini key inside
```

## Run it — one command

**Look up a single company:**
```bash
python main.py --org 923609016
```

**Generate the 1,000+ company profile dataset required for submission:**
```bash
python main.py --bulk --count 1000
```
This writes `output/company_profiles.json`, respecting the 45-minute /
2,000-request / $10 budget automatically. If the budget runs out early it
saves whatever was completed so far instead of crashing.

**Keep an existing dataset current (the "update correctly" requirement):**
```bash
python main.py --update
```
Re-fetches every company already in `output/company_profiles.json`,
detects exactly which fields changed since last time, and only regenerates
a company's summary if something factual actually changed — everything
else is left untouched. Each profile also keeps a `first_seen` date and a
`last_updated` date.

## Run the live API (for a demo / deployment)

```bash
uvicorn api.server:app --host 0.0.0.0 --port 8000
```
Then visit: `http://localhost:8000/company/923609016`

## Deploying (free, no server management)

### Option A — Render.com (free tier) with auto-deploy from GitHub Actions
1. Push this repo to GitHub (steps below).
2. Go to [render.com](https://render.com) → **New → Web Service** → connect
   your GitHub repo. Render auto-detects `render.yaml`.
3. Add your `GEMINI_API_KEY` as an environment variable in the Render
   dashboard, and pick the **Free** instance type.
4. In the Render dashboard, go to **Settings → Deploy Hook** and copy the
   URL it gives you.
5. In your GitHub repo, go to **Settings → Secrets and variables → Actions
   → New repository secret**, name it `RENDER_DEPLOY_HOOK_URL`, and paste
   the URL from step 4.
6. Done. `.github/workflows/ci.yml` now runs tests on every push, and
   automatically redeploys on Render whenever you push to `main`. If you
   skip steps 4-5, the workflow's tests still run — the deploy step just
   quietly skips itself instead of failing.

### Option B — Docker (any host)
```bash
docker build -t signalpost-agent .
docker run -p 8000:8000 --env-file .env signalpost-agent
```

## Publishing to GitHub

```bash
cd signalpost-agent
git init
git add .
git commit -m "Signalpost agent: Norwegian company info finder"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```
Then copy the **exact commit URL** (not just the repo link) for submission:
`https://github.com/<your-username>/<your-repo>/tree/<commit-hash>`
Get the commit hash with: `git rev-parse HEAD`

## Model / API details (for submission)

| Item | Value |
|---|---|
| Primary data source | Brønnøysund Enhetsregisteret (data.brreg.no) — free, no key |
| Financial data source | Brønnøysund Regnskapsregisteret (data.brreg.no) — free, no key |
| LLM used | Google Gemini 2.0 Flash (`gemini-2.0-flash`) via Google AI Studio **free tier** |
| Purpose of LLM | Summarize/explain verified registry + financial facts (not a search agent) |
| Estimated cost | **$0.00** — entirely on free tiers |
| Outbound requests | ~2,000 registry + financial calls + ~50 batched LLM calls for 1,000 companies |
| Runtime | Typically 15–25 min for 1,000 companies, comfortably under the 45-min cap |

## Submission checklist (per challenge rules)

- [ ] At least 1,000 company profiles → `output/company_profiles.json`
- [ ] Repository link → your GitHub repo
- [ ] Exact commit hash → `git rev-parse HEAD`
- [ ] One command to run it → `python main.py --bulk --count 1000`
- [ ] Model/API details → see table above
- [ ] Expected run cost → see table above
- [ ] Email the code + files to `submit@builderr.ai`
- [ ] Paste the exact commit URL on the Unstop submission form
