# FundSmart AI Complaint Triage

FundSmart complaint triage and synthetic benchmark generation project for the
Bilue AI Engineer exercise.

The repo contains two FastAPI services:

- `services/triage_service`: LLM-only complaint triage and acknowledgement
  drafting service.
- `services/sythetic_data_generation`: LLM-only batch synthetic test data
  generation service.

It also contains labelled JSONL benchmark data, Alembic migrations, Docker
Compose infrastructure, and an evaluation notebook.

## Repository Layout

```text
services/
  triage_service/
    app.py
    graph.py
    llm_client.py
    prompts.py
    schemas.py
    models.py
    db.py
  sythetic_data_generation/
    app.py
    llm_client.py
    prompts.py
    schemas.py
    reference/sample_cases.jsonl
sythetic_tests/
  synthetic_tests.jsonl
evaluation/
  triage_service_evaluation.ipynb
infra/
  Dockerfile.triage_service
  Dockerfile.sythetic_data_generation
  docker-compose.yml
alembic/
  alembic.ini
  migrations/
docs/
  Bilue_AI_Engineer_Test_Candidate_Brief.pdf
  Bilue_AI_Engineer_Test_Seed_Complaints.md
```

## Prerequisites

- Python 3.11+
- `uv`
- Docker Desktop or Docker Engine with Compose
- OpenAI API key

Install dependencies from the repo root:

```bash
uv sync
```

## Environment Setup

Configuration follows the pattern in `SETUP.md`: shared secrets live in the
root `.env`, and service-specific runtime settings live under each service.

Create a root `.env` manually:

```env
OPENAI_API_KEY=your-openai-api-key
DEFAULT_DATABASE_URL=postgresql://fundsmart:fundsmart@localhost:5433/fundsmart
REASONING_LLM_MODEL=<model>
REASONING_LLM_REASONING_EFFORT=medium
UTILITY_LLM_MODEL=<judge-or-utility-model>
UTILITY_LLM_REASONING_EFFORT=medium
```

Create the triage service env file:

```bash
cp services/triage_service/.env.example services/triage_service/.env
```

At minimum, set one of these model variables:

```env
TRIAGE_LLM_MODEL=<model>
```

or:

```env
REASONING_LLM_MODEL=<model>
```

For synthetic generation, set either:

```env
SYNTHETIC_DATA_LLM_MODEL=<model>
```

or reuse:

```env
REASONING_LLM_MODEL=<model>
```

## Triage Service

`services/triage_service` is a standalone FastAPI service. It does not use RAG,
reranking, chat memory, or heuristic fallback.

Runtime graph:

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

Run locally:

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

Use `version=v1` for the baseline prompt and `version=v2` for the improved
prompt with stronger metadata, vulnerability, regulatory, routing, and
acknowledgement instructions.

When `TRIAGE_DATABASE_URL` is configured, the service also exposes:

- `GET /triage-runs`
- `GET /triage-runs/{run_id}`
- `POST /triage-runs/{run_id}/review`

See `services/triage_service/README.md` for service-level details.

## Synthetic Data Generation Service

`services/sythetic_data_generation` generates synthetic benchmark cases in
batch. It is LLM-only and uses OpenAI structured output.

The service uses fixed seed examples from:

```text
services/sythetic_data_generation/reference/sample_cases.jsonl
```

Those samples are included as reference context when `include_seed_guidance` is
true. They teach document shape, metadata duplication, realistic complaint
style, and label conventions. Generated outputs are not written by the service;
the caller stores them externally, for example in:

```text
sythetic_tests/synthetic_tests.jsonl
```

Run locally:

```bash
uvicorn services.sythetic_data_generation.app:app --reload --port 8002
```

Health check:

```bash
curl http://localhost:8002/health
```

Generate cases:

```bash
curl -X POST http://localhost:8002/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "count": 5,
    "id_prefix": "SYN-GEN",
    "include_seed_guidance": true,
    "coverage_matrix": true,
    "output_mode": "both"
  }'
```

Response outputs include:

- `cases`
- `jsonl`
- `synthetic_complaints_jsonl`
- `gold_labels_jsonl`
- `synthetic_generation_notes_md`

See `services/sythetic_data_generation/README.md` for request fields and output
modes.

## Docker Compose

The default Docker Compose stack runs:

- `triage_service`
- PostgreSQL

The synthetic data generation service is behind a Compose profile, so normal
`up` does not start it.

PostgreSQL is exposed on host port `5433` because `5432` may already be in use.

Start the triage service stack:

```bash
docker compose --env-file .env -f infra/docker-compose.yml up -d --build triage_service
```

Service URL:

```text
http://localhost:8001
```

Database URL from the host:

```env
DEFAULT_DATABASE_URL=postgresql://fundsmart:fundsmart@localhost:5433/fundsmart
```

Start the optional synthetic data generation service:

```bash
docker compose --profile sythetic_data_generation --env-file .env -f infra/docker-compose.yml up -d --build sythetic_data_generation
```

Synthetic generation service URL:

```text
http://localhost:8002
```

Stop the service:

```bash
docker compose --env-file .env -f infra/docker-compose.yml stop triage_service
```

Stop the optional synthetic generation service:

```bash
docker compose --profile sythetic_data_generation --env-file .env -f infra/docker-compose.yml stop sythetic_data_generation
```

Bring the stack down:

```bash
docker compose --env-file .env -f infra/docker-compose.yml down
```

## Database Migrations

Alembic files live under `alembic/`.

Run migrations from the repo root:

```bash
alembic -c alembic/alembic.ini upgrade head
```

The Alembic env reads the first available database URL from:

- `DEFAULT_DATABASE_URL`
- `TRIAGE_DATABASE_URL`
- `DATABASE_URL`

It normalizes `postgresql://` to `postgresql+psycopg://` for SQLAlchemy.

## Evaluation

The evaluation notebook is:

```text
evaluation/triage_service_evaluation.ipynb
```

It calls the Docker-hosted triage service directly, using:

```text
http://localhost:8001
```

The labelled benchmark data is:

```text
sythetic_tests/synthetic_tests.jsonl
```

The notebook compares `v1` and `v2` by calling:

```text
POST /triage?version=v1
POST /triage?version=v2
```

Primary metrics are deterministic gold-label scores:

- category accuracy
- severity accuracy
- routing accuracy
- metadata accuracy
- `must_detect` recall
- `must_not_detect` violation rate
- deterministic acknowledgement safety checks

Ragas is optional and only used for acknowledgement evaluation. Enable it with:

```env
RUN_RAGAS_EVAL=true
RAGAS_LLM_MODEL=<judge-model>
```

Evaluation outputs are written under:

```text
evaluation/results/triage_service/
```

## Tests

Run all tests:

```bash
pytest -q tests
```

Current tests mock LLM clients, so they do not require live OpenAI calls.

## Service Documentation

Detailed service docs:

- `services/triage_service/README.md`
- `services/sythetic_data_generation/README.md`
