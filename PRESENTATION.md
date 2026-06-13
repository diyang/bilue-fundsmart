# FundSmart AI Complaint Triage Presentation Notes

These notes are structured for a 30-minute presentation. They are written as
speaker notes first, not as slide copy. A concise slide deck can be cut from the
section headings and bullets.

## Timing Plan

| Section | Time | Goal |
|---|---:|---|
| 1. Framing | 4 min | Show how I interpreted the real problem and scoped the solution. |
| 2. Approach and harness | 10 min | Explain architecture, schema, graph, service boundaries, and how I built it. |
| 3. Evaluation and iteration | 11 min | Explain synthetic data, evaluation notebook, v1 failures, v2 changes, and measurement. |
| 4. Next steps and questions | 5 min | Show judgement about production hardening and ask useful questions. |

---

## 1. Framing

### What I Decided The Real Problem Was

The surface request was "triage customer complaints with AI", but the real
problem is risk-sensitive intake.

For FundSmart, a complaint is not just a text classification task. The system
needs to identify the operational path and risk posture quickly enough that a
human team can respond appropriately. The high-value work is:

- Identify the complaint category.
- Detect vulnerability, hardship, responsible-lending, fraud, collections,
  self-harm, AFCA, or legal/regulatory escalation signals.
- Extract the metadata embedded in the input document.
- Route the case to the right team.
- Produce an acknowledgement draft that is helpful but does not create legal,
  financial, or conduct risk.
- Make the output measurable so prompt and schema changes can be compared.

So I treated the problem as a triage and governance pipeline, not a chatbot.

### What The System Should Optimize For

The system should optimize for:

- High recall on serious risk signals.
- Defensible routing decisions.
- Structured output that downstream systems can consume.
- Safe acknowledgement language.
- Repeatable evaluation across prompt versions.

It should not optimize only for a nice natural-language answer. A fluent but
unsafe acknowledgement is worse than a plain one. A polished summary that misses
hardship, self-harm, fraud, responsible lending, or AFCA escalation is a product
failure.

### What I Chose Not To Solve

I deliberately did not build RAG or reranking into the triage service.

Reason: the supplied task and seed complaints are single-document triage
problems. The most important information is in the complaint document itself:
header metadata, complaint body, channel, customer preference, and risk signals.
Adding retrieval would increase moving parts without solving the immediate
classification and safety problem.

I also did not build:

- End-to-end complaint resolution.
- Automatic refund, fee waiver, or credit-file correction decisions.
- A full case-management workflow.
- Real policy lookup.
- Production-grade PII redaction.
- Human review UI.
- Multi-turn customer conversation.

Those are important, but they are downstream from reliable intake. For this
exercise, I focused on making intake structured, inspectable, and testable.

### Framing Statement

My framing was:

> Build a standalone, LLM-only complaint intake service that converts one raw
> complaint document into structured triage, safe acknowledgement draft, routing,
> SLA recommendation, and persisted audit record, then evaluate v1 versus v2 with
> labelled synthetic tests.

---

## 2. Approach And Harness

## Service Architecture

The repo contains two FastAPI services:

- `services/triage_service`
- `services/sythetic_data_generation`

The triage service is the primary service. The synthetic generation service is a
supporting service used to generate benchmark cases.

The triage service is standalone:

- FastAPI HTTP API.
- LangGraph orchestration.
- OpenAI structured output through LangChain.
- PostgreSQL persistence.
- Alembic migrations.
- Docker Compose runtime.
- No RAG.
- No reranker.
- No heuristic fallback.

## Triage Service Flow

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

The key design choice is that the LLM is responsible for semantic judgement,
but the service still applies deterministic guardrails after the LLM output.

Examples:

- If the category is `financial_hardship`, the routing is forced to
  `hardship_team`.
- If the category is `fraud_or_identity`, routing is forced to
  `legal_compliance_review`.
- If self-harm is detected, routing is forced to `vulnerable_customer_team` and
  SLA becomes `urgent_review`.
- If responsible lending or AFCA appears in regulatory flags, the case is
  treated as critical risk.

This avoids treating the LLM response as the final source of truth for routing
when we already know the routing rules.

## API Input

The API accepts a `ComplaintInput` object.

The key field is:

```json
{
  "complaint_document": "..."
}
```

I deliberately renamed this away from `raw_input`. The document is not just raw
text. It is the actual complaint document that the LLM sees, including markdown
header and fenced complaint body.

Example shape:

```markdown
**Channel:** Email
**Received:** 2026-04-14 10:32 AEST
**Customer ID:** CUST-48291
**Subject:** Wrong information from your staff caused a missed payment

```
Customer complaint body...
```
```

The benchmark label metadata is not sent to the LLM as labels. Labels are only
used in the evaluation notebook.

## Schema Choices

The triage output schema is intentionally narrow and explicit:

- `category`
- `severity`
- `detected_signals`
- `vulnerability_signals`
- `regulatory_flags`
- `recommended_routing`
- `sla_recommendation`
- `customer_preferences`
- `extracted_metadata`
- `complaint_summary`
- `reasoning`

Allowed category values:

- `service_error`
- `financial_hardship`
- `responsible_lending`
- `collections`
- `fees_charges`
- `fraud_or_identity`
- `unclear_or_other`

Allowed severity values:

- `low`
- `medium`
- `high`
- `critical`

Allowed routing values:

- `frontline_complaints`
- `hardship_team`
- `responsible_lending_specialist`
- `collections_escalation`
- `vulnerable_customer_team`
- `legal_compliance_review`

Allowed SLA values:

- `standard_acknowledgement`
- `same_day_acknowledgement`
- `urgent_review`

I used structured output because free-form JSON parsing is fragile and because
the evaluation needs predictable fields.

The important schema refinement after the first evaluation run was adding
`detected_signals`. The earlier schema had vulnerability and regulatory fields,
but many benchmark labels were operational facts rather than vulnerability or
regulatory flags. Examples:

- duplicate charge
- payment dispute
- document upload issue
- wrong company or product
- credit-file concern
- collections contact
- communication preference

Those now belong in `detected_signals`, while `vulnerability_signals` and
`regulatory_flags` stay focused on risk-specific signals.

## Prompt Versions

The service supports:

- `version=v1`
- `version=v2`

### v1

v1 is intentionally basic:

- Basic prompt.
- Weaker schema guidance.
- Fewer explicit definitions.
- Fewer vulnerability and regulatory instructions.
- Less precise routing guidance.
- Basic acknowledgement safety instruction.

It acts as a baseline.

### v2

v2 adds:

- Explicit category definitions.
- Explicit severity definitions.
- Explicit routing rules.
- Explicit metadata extraction rules.
- Explicit vulnerability and regulatory signals.
- Safer acknowledgement constraints.
- Stronger instructions against inventing facts, admitting liability, or
  promising outcomes.

v2 is the iteration after seeing the likely failure modes in v1.

## Acknowledgement Validation

The acknowledgement draft is not trusted just because the first LLM produced it.

The graph validates it with:

1. A second structured LLM judge.
2. Deterministic hard-block checks.

The LLM judge returns:

- `is_valid`
- `grounded`
- `coherent`
- `safe`
- `issues`
- `revision_guidance`

The deterministic checks catch obvious unsafe language:

- Too short.
- Does not confirm receipt.
- Promises refund or waiver.
- Admits liability.
- Guarantees an outcome.
- Promises credit-file correction.

If validation fails, the graph revises the acknowledgement into a safe fallback
draft and validates again, up to a retry limit.

The reason for both LLM judge and deterministic checks is that acknowledgement
quality is partly semantic, but some safety rules should be hard constraints.

## Database And Audit Trail

When configured with `TRIAGE_DATABASE_URL`, the service stores:

- complaint id
- version
- complaint document
- input metadata
- full output JSON
- triage JSON
- acknowledgement draft
- output metadata
- created timestamp

It also supports review endpoints:

- `GET /triage-runs`
- `GET /triage-runs/{run_id}`
- `POST /triage-runs/{run_id}/review`

That gives a simple audit trail and allows later comparison between AI output
and human review.

## Docker And Runtime Harness

Docker Compose starts:

- `triage_service` on `localhost:8001`
- PostgreSQL on host port `5433`
- `sythetic_data_generation` only when its Compose profile is enabled

Normal triage startup:

```bash
docker compose --env-file .env -f infra/docker-compose.yml up -d --build triage_service
```

Health check:

```bash
curl http://localhost:8001/health
```

Expected healthy response:

```json
{
  "status": "ok",
  "provider": "openai",
  "database_enabled": true,
  "default_version": "v2"
}
```

## How I Used AI To Build It

I used AI as a pair-programming and review tool, not as an unchecked code
generator.

Concretely, I used it for:

- Reading the candidate brief and seed complaints.
- Converting the seed complaints into benchmark JSONL.
- Designing schemas for triage and generated test cases.
- Drafting prompt versions.
- Creating the FastAPI service structure using the existing `services/chatbot`
  style as a reference.
- Iterating Docker, PostgreSQL, and evaluation harness issues.
- Creating synthetic test data and split benchmark files.
- Debugging runtime failures from logs.

I still kept deterministic validation, structured schemas, tests, and
reproducible scripts because AI-generated code needs harnesses around it.

---

## 3. Evaluation And Iteration

## Synthetic Data Approach

The seed data had three strong examples:

1. Staff/service error causing missed payment and fees.
2. Subtle hardship with reduced income, separation, children, sleep distress,
   and no-phone preference.
3. Responsible lending allegation involving financial counsellor, casual
   income, job loss, arrears, collections, dependent child, and AFCA risk.

I used those as reference examples but did not stop there. The synthetic data
generation spec asks for broader failure modes, so the generation service
creates cases across a coverage matrix:

- Very short complaints.
- Vague angry complaints.
- Wrong company or wrong product.
- Hidden hardship inside a fee complaint.
- Multi-issue complaints.
- ESL-style writing.
- Sarcasm.
- Fraud or identity theft.
- Self-harm signals.
- Abusive or threatening customer.
- Contradictory information.
- Routine app bugs.

The purpose is not to create random complaints. The purpose is to generate
targeted tests that expose triage failures.

## Synthetic Data Service Flow

```text
POST /generate
-> validate request
-> load fixed sample cases from reference/sample_cases.jsonl
-> build structured LLM request
-> OpenAI structured output
-> validate requested count
-> normalize ids and output shape
-> return combined JSONL and/or split JSONL
```

The service can return:

- Combined JSONL:
  - complaint input and gold labels in one object per line.
- Split JSONL:
  - `synthetic_complaints.jsonl`
  - `gold_labels.jsonl`
  - generation notes.

I used the split format for evaluation because it makes the boundary clear:

- `synthetic_complaints.jsonl` is the input side.
- `gold_labels.jsonl` is the benchmark side.

The LLM pipeline only receives the complaint document, not the labels.

The gold labels now use a cleaner taxonomy:

- `scenario_tags`: scenario-shape coverage labels such as `sarcasm`,
  `routine_app_bug`, or `multi_issue_complaint`.
- `expected_signals`: operational facts the triage service should detect.
- `expected_preferences`: explicit customer communication preferences.
- `forbidden_signals`: structured signals the service should not emit.

The older `must_detect`, `must_not_detect`, and `customer_preferences` fields
are still supported for backward compatibility, but the evaluator separates
them into the cleaner taxonomy before scoring.

## Evaluation Harness

The evaluation notebook is:

```text
evaluation/triage_service_evaluation.ipynb
```

It is run via Papermill:

```bash
scripts/run_triage_service_evaluation.sh
```

The runner:

- Calls the Docker-hosted service directly.
- Passes notebook parameters through Papermill `-p`.
- Supports split and combined benchmark data.
- Creates timestamped output directories.
- Writes `summary.json`, `case_scores.jsonl`, `failures.jsonl`, and optional
  Ragas output into the same timestamped run directory as the executed notebook.
- Keeps per-attempt notebooks and logs.
- Retries failed notebook runs.
- Deletes attempt files after success.
- Shows progress for every case and version.

The notebook compares:

- `POST /triage?version=v1`
- `POST /triage?version=v2`

For each case and version, it records:

- request success or error
- category match
- severity match
- routing match
- operational signal recall
- customer preference recall
- scenario tag recall, reported separately from end-to-end pass/fail
- forbidden structured-signal false positives
- metadata extraction accuracy
- acknowledgement safety
- end-to-end pass/fail
- latency

It writes:

- summary JSON
- per-case score JSONL
- failures JSONL
- optional Ragas acknowledgement scores

These are written into the timestamped Papermill run directory, for example:

```text
evaluation/results/triage_service/papermill_runs/20260613_215536/
  triage_service_evaluation_executed.ipynb
  summary.json
  case_scores.jsonl
  failures.jsonl
```

## Metrics

Core deterministic metrics:

- `category_accuracy`
- `severity_accuracy`
- `routing_accuracy`
- `must_detect_recall`
- `operational_signal_recall`
- `preference_recall`
- `scenario_tag_recall`
- `no_forbidden_signal_rate`
- `metadata_accuracy`
- `acknowledgement_safety_rate`
- `end_to_end_pass_rate`
- `mean_latency_seconds`

For the presentation, pull the final numbers from:

```text
evaluation/results/triage_service/papermill_runs/<timestamp>/
```

or from the executed notebook output tables:

- `summary`
- `pivot`
- `failures`
- `by_scenario`

## Optional Ragas Evaluation

Ragas is not used for triage labels.

I use Ragas only as an optional acknowledgement-quality judge, because
acknowledgement quality is free-text and has semantic properties:

- Groundedness.
- Coherence.
- Safety/compliance.

The deterministic benchmark remains the source of truth for:

- category
- severity
- routing
- metadata
- signal detection

Ragas is useful as a second lens on the acknowledgement draft, not as the whole
evaluation framework.

## What v1 Is Expected To Get Wrong

v1 is expected to fail more often on:

- Hidden hardship in a routine fee complaint.
- Responsible-lending cases where the wording is indirect.
- AFCA/legal escalation.
- Self-harm or safety signals.
- Distinguishing service error from hardship.
- Distinguishing wrong-company complaints from real FundSmart complaints.
- Extracting metadata consistently.
- Respecting communication preferences.
- Avoiding over-promising in acknowledgements.

The point of v1 is to show that "basic structured output" is not enough for a
risk-sensitive complaints workflow.

## What v2 Changed

v2 changed the instructions and guardrails:

- More explicit category definitions.
- More explicit severity definitions.
- More explicit routing rules.
- Better metadata extraction instructions.
- Clear vulnerability signal expectations.
- Clear regulatory flag expectations.
- Safer acknowledgement instructions.
- Deterministic escalation/routing guardrails after LLM output.
- LLM acknowledgement judge plus hard-block checks.

Expected improvement:

- Higher recall on hardship, responsible lending, fraud, self-harm, AFCA, and
  collections signals.
- More consistent routing.
- Better SLA alignment.
- Better metadata extraction.
- Safer acknowledgement drafts.

## What I Would Show In The Presentation

Use three examples rather than reading the whole benchmark:

1. A subtle hardship case:
   - Why it looks like a normal fee/payment complaint.
   - Why it should route to hardship.
   - How v2 handles vulnerability signals and communication preference.

2. A responsible-lending case:
   - Why financial counsellor, casual income, job loss, affordability, arrears,
     collections, and AFCA matter.
   - Why this should route to a specialist path, not frontline complaints.

3. A wrong-company or vague complaint:
   - Why over-escalation is also a failure.
   - Why `unclear_or_other` and `frontline_complaints` are sometimes correct.

Then show one failure table row where v2 still missed something, because that
demonstrates how the harness drives the next iteration.

## Current Known Runtime Lessons

One useful implementation lesson came from the evaluation run itself.

The service was completing the LLM triage, but the API requests failed after the
LLM call because database persistence rejected the UUID type:

```text
psycopg.ProgrammingError: cannot adapt type 'UUID'
```

The fix was to convert `uuid_utils.uuid7()` into a standard-library
`uuid.UUID` before persisting. That is exactly why the evaluation harness calls
the service as a black box instead of only unit-testing functions.

It caught an integration failure across:

- LLM output
- graph
- FastAPI response path
- SQLAlchemy model
- psycopg
- PostgreSQL

---

## 4. What I Would Do Next

## Product And Risk Improvements

1. Add human review workflow.

   Store the AI output, human edits, final category, final routing, and final
   acknowledgement. Use that to measure model drift and build better labels.

2. Add PII and sensitive-data handling.

   Redact or classify sensitive personal information before sending text to any
   external LLM provider, depending on FundSmart policy and risk appetite.

3. Add policy-backed response generation.

   I avoided RAG for triage, but acknowledgement and next-step copy may benefit
   from retrieval over approved policy wording, hardship process copy, complaint
   handling timelines, and escalation instructions.

4. Add confidence and review thresholds.

   The system should be able to say "route to human review immediately" based
   on uncertainty, conflicting signals, or critical-risk indicators.

5. Expand benchmark data.

   Add more human-authored and human-reviewed cases, not only synthetic data.
   Synthetic data is good for coverage, but production quality needs real
   distribution examples and expert labels.

6. Monitor live performance.

   Track:

   - triage category agreement with humans
   - severity agreement with humans
   - routing override rate
   - acknowledgement edit rate
   - high-risk false negatives
   - high-risk false positives
   - latency
   - cost per complaint

## Engineering Improvements

1. Add request tracing.

   Add correlation ids through FastAPI, graph steps, LLM calls, and database
   records.

2. Add structured logging.

   Log model version, prompt version, graph version, case id, latency, retries,
   validation issues, and final routing.

3. Add migration discipline.

   Use Alembic migrations for schema changes and avoid relying only on
   `create_all` in production.

4. Add CI.

   Run unit tests, schema tests, notebook smoke tests, Docker build checks, and
   sample evaluation checks in CI.

5. Add model/prompt registry.

   Version prompts and schemas together so evaluation results can be reproduced.

6. Add provider abstraction tests.

   The service is currently OpenAI-only by design. If multiple LLM providers are
   needed, add provider contract tests before adding runtime choice.

## Questions For Bilue / FundSmart

These are the questions I would ask before productionizing:

1. What is the target operating model?

   Is this a decision-support tool for complaints agents, or should it
   auto-route cases without human review?

2. Which categories and teams are real?

   Are `hardship_team`, `responsible_lending_specialist`, and
   `vulnerable_customer_team` operationally accurate, or should routing map to
   existing queues?

3. What is the risk tolerance for false negatives?

   Especially for hardship, self-harm, fraud, responsible lending, and AFCA.

4. What language is approved for acknowledgements?

   Should acknowledgements be free-drafted, template-constrained, or retrieved
   from an approved content library?

5. What data can be sent to an external LLM?

   Are customer identifiers, transcript text, hardship details, or health
   disclosures allowed? Do we need redaction or local hosting?

6. What systems would this integrate with?

   CRM, complaints case manager, collections platform, identity/fraud workflow,
   document store, or messaging platform?

7. What are the regulatory response-time requirements?

   Should SLA recommendation be based only on severity, or should it encode
   formal complaint-handling obligations?

8. What historical labels are available?

   Do we have resolved complaints with final categories, routes, outcomes, and
   human acknowledgements?

9. Who owns prompt and policy changes?

   Engineering, risk/compliance, complaints operations, or a joint governance
   process?

10. What level of explainability is required?

    Should every signal and routing decision be explainable to an agent,
    auditor, or regulator?

---

## Suggested Slide Outline

### Slide 1: Title

FundSmart AI Complaint Triage

One-line summary:

> LLM-only structured triage service with risk guardrails, acknowledgement
> validation, synthetic benchmark generation, and Papermill evaluation.

### Slide 2: Problem Framing

- Not a chatbot.
- Risk-sensitive complaint intake.
- Optimize for high-risk recall, routing, metadata, and safe acknowledgement.

### Slide 3: Scope

Solved:

- Single complaint document to structured triage.
- Routing and SLA.
- Acknowledgement draft and validation.
- Synthetic benchmark and evaluation harness.

Not solved:

- Full resolution.
- Real policy retrieval.
- Human UI.
- Multi-turn conversation.

### Slide 4: Architecture

Show:

```text
FastAPI -> LangGraph -> OpenAI structured output -> guardrails -> judge -> DB
```

### Slide 5: Schema

Show the important fields:

- category
- severity
- detected signals
- regulatory flags
- vulnerability signals
- routing
- SLA
- metadata
- acknowledgement

### Slide 6: v1 vs v2

v1:

- Basic prompt.
- Weak definitions.
- Fewer safety instructions.

v2:

- Explicit definitions.
- Explicit metadata extraction.
- Explicit vulnerability/regulatory handling.
- Deterministic routing.
- Acknowledgement judge.

### Slide 7: Synthetic Data

- Seed examples became local reference knowledge.
- Generated coverage matrix cases.
- Split input file from gold-label file.
- Gold labels split scenario tags, expected signals, expected preferences, and
  forbidden signals.
- Labels are only used in evaluation.

### Slide 8: Evaluation Harness

- Docker-hosted service.
- Papermill notebook.
- v1/v2 comparison.
- Deterministic metrics.
- Timestamped run outputs containing the executed notebook, summary, case
  scores, and failures.
- Optional Ragas acknowledgement evaluation.
- Progress and retry logs.

### Slide 9: Results

Fill from latest notebook:

| Metric | v1 | v2 | Delta |
|---|---:|---:|---:|
| Category accuracy | TBD | TBD | TBD |
| Severity accuracy | TBD | TBD | TBD |
| Routing accuracy | TBD | TBD | TBD |
| Must-detect recall | TBD | TBD | TBD |
| Operational signal recall | TBD | TBD | TBD |
| Preference recall | TBD | TBD | TBD |
| Scenario tag recall | TBD | TBD | TBD |
| Metadata accuracy | TBD | TBD | TBD |
| Acknowledgement safety | TBD | TBD | TBD |
| End-to-end pass rate | TBD | TBD | TBD |

Presentation note:

> `scenario_tag_recall` is a coverage diagnostic, not part of end-to-end triage
> pass/fail. End-to-end pass/fail is based on category, severity, routing,
> operational signals, preferences, forbidden structured signals, metadata, and
> acknowledgement safety.

### Slide 10: Failure Example

Use one row from `failures`.

Talk through:

- What the complaint said.
- What the expected label was.
- What the model got wrong.
- What I changed or would change next.

### Slide 11: Runtime Lesson

The UUID persistence issue:

- LLM succeeded.
- DB write failed.
- Black-box evaluation caught it.
- Fixed standard UUID conversion.

### Slide 12: Next Steps

- Human review loop.
- PII/redaction.
- Approved acknowledgement content.
- More real labelled data.
- Monitoring and drift.
- CI and prompt/schema versioning.

### Slide 13: Questions

Pick 3-5 questions from the list above.

---

## Demo Script

### 1. Start Service

```bash
docker compose --env-file .env -f infra/docker-compose.yml up -d --build triage_service
```

### 2. Health Check

```bash
curl http://localhost:8001/health
```

Expected:

```json
{
  "status": "ok",
  "provider": "openai",
  "database_enabled": true,
  "default_version": "v2"
}
```

### 3. Run Evaluation

```bash
scripts/run_triage_service_evaluation.sh
```

### 4. Show Outputs

Open the newest folder:

```text
evaluation/results/triage_service/papermill_runs/<timestamp>/
```

Show:

- executed notebook
- `summary.json`
- `case_scores.jsonl`
- `failures.jsonl`
- attempt logs, if useful

### 5. Explain One Case

Choose one case from:

```text
sythetic_tests/synthetic_complaints.jsonl
sythetic_tests/gold_labels.jsonl
```

Then show the corresponding v1/v2 scoring row.

---

## Closing Statement

The main design decision was to treat complaint triage as a governed intake
workflow rather than a text-generation problem.

The LLM handles semantic extraction and judgement, but the system constrains it
with:

- typed schemas
- deterministic routing guardrails
- acknowledgement validation
- persistence
- black-box evaluation
- synthetic coverage tests

That gives a practical path from prototype to production: measure where the
model fails, improve prompt/schema/guardrails, and keep humans in the loop for
high-risk decisions.
