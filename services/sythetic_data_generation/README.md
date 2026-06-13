# FundSmart Synthetic Data Generation Service

Standalone FastAPI service for generating synthetic complaint triage benchmark
cases in batches.

The service returns structured cases plus JSONL strings compatible with both the
current combined benchmark file and the split-file format from
`synthetic_test_case_generation_spec.md`.

```text
sythetic_tests/synthetic_tests.jsonl
data/synthetic_complaints.jsonl
data/gold_labels.jsonl
data/synthetic_generation_notes.md
```

## Run

```bash
uvicorn services.sythetic_data_generation.app:app --reload --port 8002
```

Generate five cases:

```bash
curl -X POST http://localhost:8002/generate \
  -H 'Content-Type: application/json' \
  -d '{"count":5,"id_prefix":"SYN-GEN","output_mode":"both"}'
```

Response fields:

- `cases`: structured generated test cases
- `jsonl`: combined JSONL with complaint document and benchmark labels
- `synthetic_complaints_jsonl`: split complaint-input JSONL
- `gold_labels_jsonl`: split expected-label JSONL
- `synthetic_generation_notes_md`: coverage-matrix notes

Use OpenAI structured output. The service always uses an LLM provider:

```bash
export SYNTHETIC_DATA_LLM_PROVIDER=openai
export SYNTHETIC_DATA_LLM_MODEL=<model>
uvicorn services.sythetic_data_generation.app:app --reload --port 8002
```

If `SYNTHETIC_DATA_LLM_MODEL` is not set, `REASONING_LLM_MODEL` is used as the
model name.
