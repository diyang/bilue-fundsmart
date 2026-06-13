# FundSmart Triage Assistant

Standalone FastAPI complaint triage service for the Bilue AI Engineer exercise.

The main service lives in `services/triage_service/`. It accepts a single complaint with
`complaint_document`, produces structured triage and an acknowledgement draft,
and can optionally persist triage runs to Postgres when `TRIAGE_DATABASE_URL` is
set.

Run locally:

```bash
export TRIAGE_LLM_MODEL=<model>
uvicorn services.triage_service.app:app --reload --port 8001
```
