# FundSmart Triage Service

FastAPI service for single-turn FundSmart complaint triage and acknowledgement
drafting.

The service accepts one complaint document, sends only `complaint_document` to
the LLM pipeline, returns structured triage labels, drafts an acknowledgement,
and optionally persists each run to PostgreSQL for later review.

## What It Does

- Classifies complaints into FundSmart triage categories.
- Extracts metadata from the complaint document header.
- Detects vulnerability, regulatory, safety, fraud, collections, hardship, and
  responsible-lending signals.
- Applies deterministic routing guardrails after LLM triage.
- Drafts a customer acknowledgement for human review.
- Uses a second structured LLM judge to validate acknowledgement groundedness,
  coherence, and safety.
- Applies deterministic hard-block acknowledgement checks for obvious unsafe
  language such as liability admissions or promised refunds.

It does not use RAG, reranking, or chat memory.

## Prerequisites

From the repo root:

```bash
uv sync
```

The service requires an OpenAI API key and an LLM model. Configuration follows
the repo setup pattern:

- root `.env`: shared secrets such as `OPENAI_API_KEY`
- `services/triage_service/.env`: triage service runtime settings

Create the service env file:

```bash
cp services/triage_service/.env.example services/triage_service/.env
```

At minimum, set one of:

```env
TRIAGE_LLM_MODEL=<model>
```

or:

```env
REASONING_LLM_MODEL=<model>
```

The service is LLM-only. There is no heuristic fallback.

## Run Locally

From the repo root:

```bash
uvicorn services.triage_service.app:app --reload --port 8001
```

Health check:

```bash
curl http://localhost:8001/health
```

Triage one complaint:

```bash
curl -X POST 'http://localhost:8001/triage?version=v2' \
  -H 'Content-Type: application/json' \
  -d '{
    "id": "demo-001",
    "complaint_document": "**Channel:** Email\n**Received:** 2026-04-18 09:12 AEST\n**Customer ID:** CUST-DEMO\n\n```\nYou charged me twice this month. Fix it and refund me.\n```"
  }'
```

Use `version=v1` for the baseline prompt and `version=v2` for the stronger
prompt with explicit metadata, vulnerability, regulatory, routing, and
acknowledgement instructions.

## Run With Docker Compose

The compose stack also starts PostgreSQL on host port `5433`.

From the repo root:

```bash
docker compose --env-file .env -f infra/docker-compose.yml up -d --build triage_service
```

Service URL:

```text
http://localhost:8001
```

PostgreSQL URL from the host:

```env
DEFAULT_DATABASE_URL=postgresql://fundsmart:fundsmart@localhost:5433/fundsmart
```

Inside Docker Compose, the service uses:

```env
TRIAGE_DATABASE_URL=postgresql+psycopg://fundsmart:fundsmart@postgresql:5432/fundsmart
TRIAGE_DATABASE_AUTO_CREATE=true
```

Stop the service:

```bash
docker compose --env-file .env -f infra/docker-compose.yml stop triage_service
```

Bring the stack down:

```bash
docker compose --env-file .env -f infra/docker-compose.yml down
```

## Database And Review Endpoints

When `TRIAGE_DATABASE_URL` is configured:

- `POST /triage` stores each triage run and returns `run_id`
- `GET /triage-runs` lists recent runs
- `GET /triage-runs/{run_id}` retrieves one run
- `POST /triage-runs/{run_id}/review` stores human review feedback

If `TRIAGE_SERVICE_API_KEY` is set, call protected endpoints with:

```text
Authorization: Bearer <TRIAGE_SERVICE_API_KEY>
```

## Graph Flow

```text
POST /triage
-> normalise_complaint
-> triage_complaint
   -> OpenAI structured output: TriageLLMOutput
-> risk_safety_check
-> set_urgent_escalation_routing or set_standard_routing
-> validate_acknowledgement
   -> OpenAI structured output: AcknowledgementJudgeOutput
   -> deterministic hard safety checks
-> revise_acknowledgement when invalid, up to retry limit
-> save_output
-> optional database persistence
-> API response
```

## Runtime Configuration

Common env vars:

```env
OPENAI_API_KEY=...
TRIAGE_LLM_MODEL=<model>
TRIAGE_LLM_REASONING_EFFORT=medium
TRIAGE_SERVICE_API_KEY=
TRIAGE_SERVICE_LOG_LEVEL=INFO
TRIAGE_DATABASE_URL=postgresql+psycopg://fundsmart:fundsmart@localhost:5433/fundsmart
TRIAGE_DATABASE_AUTO_CREATE=true
```

If `TRIAGE_LLM_MODEL` is not set, `REASONING_LLM_MODEL` is used.

## Tests

From the repo root:

```bash
pytest -q tests
```
