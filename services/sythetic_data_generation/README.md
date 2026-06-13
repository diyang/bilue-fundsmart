# FundSmart Synthetic Data Generation Service

FastAPI service for generating synthetic FundSmart complaint triage benchmark
cases in batches.

The service uses an LLM to create new complaint documents and matching gold
labels for evaluating `services/triage_service`.

## What It Does

- Generates synthetic complaint test cases in batch.
- Produces the raw LLM input field, `complaint_document`.
- Produces benchmark metadata and labels:
  - `expected_category`
  - `expected_severity`
  - `expected_routing`
  - `expected_sla`
  - `must_detect`
  - `must_not_detect`
  - `customer_preferences`
- Returns combined JSONL compatible with `sythetic_tests/synthetic_tests.jsonl`.
- Returns optional split-file outputs matching
  `synthetic_test_case_generation_spec.md`.
- Uses fixed seed samples from `reference/sample_cases.jsonl` as a small
  service-local knowledge base.

The service is LLM-only. There is no heuristic generation path.

## Fixed Sample Knowledge Base

Seed examples live in:

```text
services/sythetic_data_generation/reference/sample_cases.jsonl
```

When `include_seed_guidance` is true, the service includes that JSONL in the LLM
request as reference context. The samples teach:

- complaint document shape
- metadata/header duplication
- realistic FundSmart complaint style
- label conventions for sample service error, hardship, and responsible-lending
  cases

The model is instructed not to copy the seed complaints or reuse their customer
IDs. Generated outputs should be stored outside the service, for example:

```text
sythetic_tests/synthetic_tests.jsonl
```

## Prerequisites

From the repo root:

```bash
uv sync
```

The service requires an OpenAI API key and an LLM model. Configuration follows
the repo setup pattern:

- root `.env`: shared secrets such as `OPENAI_API_KEY`
- shell env or service env: synthetic generation runtime settings

At minimum, set one of:

```env
SYNTHETIC_DATA_LLM_MODEL=<model>
```

or:

```env
REASONING_LLM_MODEL=<model>
```

`SYNTHETIC_DATA_LLM_PROVIDER` defaults to `openai`. The only supported provider
is `openai`.

## Run Locally

From the repo root:

```bash
uvicorn services.sythetic_data_generation.app:app --reload --port 8002
```

Health check:

```bash
curl http://localhost:8002/health
```

## Run With Docker Compose

This service is behind a Compose profile, so it is not started by a normal
`docker compose up`.

Start it explicitly from the repo root:

```bash
docker compose --profile sythetic_data_generation --env-file .env -f infra/docker-compose.yml up -d --build sythetic_data_generation
```

Service URL:

```text
http://localhost:8002
```

Stop it:

```bash
docker compose --profile sythetic_data_generation --env-file .env -f infra/docker-compose.yml stop sythetic_data_generation
```

Generate five cases:

```bash
curl -X POST http://localhost:8002/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "count": 5,
    "id_prefix": "SYN-GEN",
    "output_mode": "both"
  }'
```

Generate focused hardship cases:

```bash
curl -X POST http://localhost:8002/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "count": 3,
    "id_prefix": "SYN-HARD",
    "scenario_focus": ["hidden_hardship_in_fee_complaint"],
    "category_focus": ["financial_hardship"],
    "include_seed_guidance": true,
    "coverage_matrix": true,
    "output_mode": "combined"
  }'
```

If `SYNTHETIC_DATA_SERVICE_API_KEY` is set, call protected endpoints with:

```text
Authorization: Bearer <SYNTHETIC_DATA_SERVICE_API_KEY>
```

## Request Shape

```json
{
  "count": 10,
  "id_prefix": "SYN-GEN",
  "scenario_focus": [],
  "category_focus": [],
  "include_seed_guidance": true,
  "coverage_matrix": true,
  "output_mode": "both",
  "notes": null
}
```

Useful fields:

- `count`: number of cases to return, from 1 to 50.
- `id_prefix`: prefix used when the service normalizes IDs.
- `scenario_focus`: optional scenario types to emphasize.
- `category_focus`: optional category labels to emphasize.
- `include_seed_guidance`: include `reference/sample_cases.jsonl` in the LLM
  request.
- `coverage_matrix`: prefer broad scenario coverage instead of generic random
  generation.
- `output_mode`: `combined`, `split`, or `both`.
- `notes`: optional extra instructions for the batch.

## Response Outputs

The response includes:

- `cases`: structured generated test cases.
- `jsonl`: combined JSONL with complaint input and gold labels.
- `synthetic_complaints_jsonl`: split complaint-input JSONL.
- `gold_labels_jsonl`: split expected-label JSONL.
- `synthetic_generation_notes_md`: generation notes and coverage summary.
- `provider`, `model`, `latency_seconds`.

Output mode behavior:

```text
combined -> jsonl only
split    -> synthetic_complaints_jsonl, gold_labels_jsonl, notes
both     -> combined and split outputs
```

The service verifies the LLM returned exactly the requested number of cases. If
not, it returns `HTTP 502`.

## Flow

```text
POST /generate
-> validate SyntheticGenerationRequest
-> load OpenAI synthetic data client
-> load reference/sample_cases.jsonl when include_seed_guidance=true
-> build system prompt and request JSON message
-> OpenAI structured output: SyntheticBatchOutput
-> verify generated count equals requested count
-> normalize IDs and force source=synthetic
-> build combined and/or split JSONL outputs
-> return SyntheticGenerationResponse
```

## Runtime Configuration

Common env vars:

```env
OPENAI_API_KEY=...
SYNTHETIC_DATA_LLM_MODEL=<model>
SYNTHETIC_DATA_LLM_REASONING_EFFORT=medium
SYNTHETIC_DATA_SERVICE_API_KEY=
SYNTHETIC_DATA_SERVICE_LOG_LEVEL=INFO
```

If `SYNTHETIC_DATA_LLM_MODEL` is not set, `REASONING_LLM_MODEL` is used.

## Tests

From the repo root:

```bash
pytest -q tests
```
