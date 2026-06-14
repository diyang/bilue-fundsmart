# FundSmart AI Complaint Triage

Setup and usage guide for the FundSmart complaint triage project.

For the detailed project report, read [REPORT.md](REPORT.md).

## Prerequisites

- Python 3.11+
- `uv`
- Docker Desktop or Docker Engine with Compose
- OpenAI API key
- `jq` if exporting synthetic JSONL files

Install dependencies:

```bash
uv sync
```

## Environment Setup

Create service env files:

```bash
cp services/triage_service/.env.example services/triage_service/.env
cp services/sythetic_data_generation/.env.example services/sythetic_data_generation/.env
```

Create or update root `.env`:

```env
OPENAI_API_KEY=your-openai-api-key
DEFAULT_DATABASE_URL=postgresql://fundsmart:fundsmart@localhost:5433/fundsmart

REASONING_LLM_MODEL=<model>
REASONING_LLM_REASONING_EFFORT=medium
UTILITY_LLM_MODEL=<judge-or-utility-model>
UTILITY_LLM_REASONING_EFFORT=medium
```

Model selection:

- `TRIAGE_LLM_MODEL` overrides `REASONING_LLM_MODEL` for triage.
- `SYNTHETIC_DATA_LLM_MODEL` overrides `REASONING_LLM_MODEL` for synthetic generation.

Optional API keys:

```env
TRIAGE_SERVICE_API_KEY=
SYNTHETIC_DATA_SERVICE_API_KEY=
```

## Run The Triage Service

Start PostgreSQL and the triage service:

```bash
docker compose --env-file .env -f infra/docker-compose.yml up -d --build
```

Check health:

```bash
uv run triage health
```

Stop the stack:

```bash
docker compose --env-file .env -f infra/docker-compose.yml down
```

## Use The Triage CLI

Send a formatted complaint document:

```bash
uv run triage send sample_complains/sample1.txt
```

Example CLI output:

![FundSmart triage CLI example](figures/triage_example.png)

Return raw JSON:

```bash
uv run triage send sample_complains/sample1.txt --json
```

Send a plain `.txt` complaint body and provide metadata from the CLI:

```bash
uv run triage send complaint.txt \
  --channel Email \
  --received "2026-05-01 09:00 AEST" \
  --customer-id CUST-123 \
  --subject "Payment showing overdue after I paid"
```

Pipe complaint text:

```bash
cat complaint.txt | uv run triage send --channel SMS
```

Use the baseline version:

```bash
uv run triage send sample_complains/sample1.txt --version v1
```

CLI help:

```bash
uv run triage --help
uv run triage send --help
```

Input behavior:

- Files with headers such as `**Channel:**` and `**Received:**` are sent as the
  full `complaint_document`.
- Plain text files are wrapped into the same markdown complaint-document shape
  using metadata options supplied on the command line.

## Use The Triage API

Health:

```bash
curl http://localhost:8001/health
```

Triage one complaint:

````bash
curl -X POST 'http://localhost:8001/triage?version=v2' \
  -H 'Content-Type: application/json' \
  -d '{
    "id": "demo-001",
    "source": "manual",
    "complaint_document": "**Channel:** Email\n**Received:** 2026-05-01 09:00 AEST\n**Customer ID:** CUST-123\n\n```\nI paid yesterday but the app still says I am overdue.\n```"
  }'
````

Use `version=v1` for the baseline pipeline and `version=v2` for the improved
pipeline.

## Run Synthetic Data Generation

Start the optional synthetic data generation service:

```bash
docker compose --profile sythetic_data_generation --env-file .env -f infra/docker-compose.yml up -d --build sythetic_data_generation
```

Generate 10 cases and export all useful artifacts:

```bash
curl -s -X POST http://localhost:8002/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "count": 10,
    "id_prefix": "SYN-GEN",
    "include_seed_guidance": true,
    "coverage_matrix": true,
    "output_mode": "both"
  }' > /tmp/synthetic_response.json

jq -r '.jsonl' /tmp/synthetic_response.json > data/sythetic_tests/synthetic_generated.jsonl
jq -r '.synthetic_complaints_jsonl' /tmp/synthetic_response.json > data/sythetic_tests/synthetic_complaints.jsonl
jq -r '.gold_labels_jsonl' /tmp/synthetic_response.json > data/sythetic_tests/gold_labels.jsonl
jq -r '.synthetic_generation_notes_md' /tmp/synthetic_response.json > data/sythetic_tests/synthetic_generation_notes.md
```

Stop only the synthetic data service:

```bash
docker compose --profile sythetic_data_generation --env-file .env -f infra/docker-compose.yml stop sythetic_data_generation
```

## Database Migrations

Run Alembic migrations:

```bash
alembic -c alembic/alembic.ini upgrade head
```

PostgreSQL is exposed on host port `5433`.

For GUI/JDBC tools use:

```text
jdbc:postgresql://localhost:5433/fundsmart
```

For SQLAlchemy/Alembic use:

```env
DEFAULT_DATABASE_URL=postgresql://fundsmart:fundsmart@localhost:5433/fundsmart
```

## Tests

Run tests:

```bash
pytest -q tests
```

## More Detail

For the detailed project report, read [REPORT.md](REPORT.md).
