# Signalpost Agent — Company Research with Provenance

This repository is a request-safe implementation for the Signalpost challenge.

## Important fixes in this version

### 1. `python main.py --bulk --count 1000` really handles 1,000

The old implementation first paged the registry for 1,000 organisation numbers and
then made another registry request for each company. That creates about:

- 10 list requests
- 1,000 company-detail requests
- 1,000 accounts requests
- plus Gemini requests

That can cross the evaluator's 2,000 outbound-request ceiling.

This version fixes the problem by reusing the company records returned by the
official registry listing endpoint. For the normal bulk fallback, the expected
shape is approximately:

- ~10 registry-list requests for 1,000 companies
- 1,000 accounts-register requests
- 0 external LLM requests by default
- **~1,010 outbound requests total**

If `company_numbers.txt` is supplied, the agent processes those exact organisation
numbers. That path uses one detail request + one accounts request per company, so
1,000 companies use exactly 2,000 requests before retries. The default bulk command
therefore uses local summaries and does not spend extra requests on Gemini.

Every retry is counted before the outbound attempt, so the request counter matches
the challenge's "retries count" rule.

### 2. Gemini 2.0 Flash is removed

Google shut down `gemini-2.0-flash` on June 1, 2026. The default is now
`gemini-3.5-flash-lite`. Gemini is optional in this repository; the core bulk
dataset can be produced without an API key.

### 3. No fake financial values

Missing financial data remains `null`. The code never changes missing values to
zero and never asks the LLM to invent figures.

### 4. Evidence and dates are kept with each profile

Each profile contains:

- `source_url` for the company registry record
- `financial_source_url` when an accounts record is available
- `sources[]` with source type, URL, retrieval timestamp and reporting period
- `first_seen`, `last_updated`, `changed_fields`
- `fetched_at`

## Run

### Required 1,000-profile command

```powershell
python main.py --bulk --count 1000
```

This is the safe default and does **not** require a Gemini API key.

Output:

```text
output/company_profiles.json
```

### Use the supplied organisation-number list

Put one organisation number per line in `company_numbers.txt`, then run:

```powershell
python main.py --bulk --count 1000
```

Or specify another file:

```powershell
python main.py --bulk --count 1000 --org-list path	o\company_numbers.txt
```

The file is never uploaded to GitHub if it contains real data: `.gitignore`
should be used for any private/supplied list if required by the challenge.

### Single-company lookup

```powershell
python main.py --org 923609016
```

### Refresh existing profiles

```powershell
python main.py --update
```

Refresh is designed to be idempotent: it compares tracked fields, records real
changes and keeps the previous summary when nothing factual changed.

### Optional Gemini summaries

Create `.env` from `.env.example` and add your key, then:

```powershell
python main.py --org 923609016 --llm
```

For a bulk run:

```powershell
python main.py --bulk --count 1000 --llm
```

The program calculates whether enough request budget remains for all Gemini
summary batches. If not, it skips the Gemini phase instead of breaking the
1,000-profile run.

## API

Install dependencies and run:

```powershell
uvicorn api.server:app --host 0.0.0.0 --port 8000
```

Then:

```text
GET /health
GET /company/{organisation_number}
```

The API uses Gemini only when `GEMINI_API_KEY` is present; otherwise it returns a
deterministic, evidence-based local summary.

## Data sources

Primary source:

https://data.brreg.no/enhetsregisteret/api

Financial source:

https://data.brreg.no/regnskapsregisteret/regnskap

Gemini API documentation:

https://ai.google.dev/gemini-api/docs

## Request/cost safety

Daily evaluator limits are configured as:

- 45 minutes
- 2,000 outbound requests
- $10 declared external API cost

The `BudgetGuard` reserves a request immediately before every outbound attempt,
including retries. A run stops cleanly at the boundary and saves completed
profiles rather than crashing.

## Tests

```powershell
python -m pytest tests -v
python -m py_compile main.py src/*.py api/*.py tests/*.py
```

## Project structure

```text
signalpost-agent/
├── main.py
├── company_numbers.txt       # optional local input list
├── src/
│   ├── agent.py
│   ├── brreg_client.py
│   ├── budget_guard.py
│   ├── config.py
│   ├── llm_client.py
│   ├── models.py
│   └── regnskap_client.py
├── api/server.py
├── tests/
├── output/
├── requirements.txt
├── Dockerfile
├── render.yaml
└── .env.example
```

## Submission note

The challenge currently asks for at least 1,000 profiles, the organisation-number
list used, repository link, exact commit hash, one reproducible run command,
model/API/licence details, and expected cost per 100-company run. Check the
current Builderr challenge page and evaluation contract before submitting because
the organiser controls the final harness and requirements.
