# FundSmart Triage Service

Standalone FastAPI single-turn complaint triage pipeline for the Bilue AI Engineer
test.

The pipeline reads one complaint document, sends only `complaint_document` to
the triage client, produces structured triage, drafts an acknowledgement for
human review, and returns a structured recommendation for a human agent to
review.

It does not use RAG, reranking, or chat memory.
It persists triage runs only when a Postgres database URL is configured.

## Run

Start the API:

```bash
uvicorn triage_service.app:app --reload --port 8001
```

Send one complaint:

```bash
curl -X POST 'http://localhost:8001/triage?version=v2' \
  -H 'Content-Type: application/json' \
  -d '{"id":"demo","complaint_document":"**Channel:** Email\n\n```\nYou charged me twice this month. Fix it and refund me.\n```"}'
```

By default the service uses a deterministic local heuristic client so the harness
is runnable without API keys. To use OpenAI structured output instead:

```bash
export TRIAGE_LLM_PROVIDER=openai
export TRIAGE_LLM_MODEL=<model>
uvicorn triage_service.app:app --reload --port 8001
```

## Database

Set `TRIAGE_DATABASE_URL` to enable persistence. `DATABASE_URL` is used as a
fallback.

```bash
export TRIAGE_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/fundsmart
export TRIAGE_DATABASE_AUTO_CREATE=true
uvicorn triage_service.app:app --reload --port 8001
```

When persistence is enabled:

- `POST /triage` stores each triage run and returns `run_id`
- `GET /triage-runs` lists recent runs
- `GET /triage-runs/{run_id}` retrieves one run
- `POST /triage-runs/{run_id}/review` stores human review feedback

`v1` is the baseline prompt version. `v2` is the improved default version.
