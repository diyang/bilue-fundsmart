"""Prompting for FundSmart synthetic complaint test data generation."""

SYNTHETIC_GENERATION_PROMPT = """
You generate synthetic benchmark data for FundSmart, a fictional Australian
digital consumer lender.

The generated data is for evaluating an AI complaint triage and acknowledgement
pipeline. It must be realistic enough to expose classification, severity,
vulnerability, regulatory or escalation flags, routing, SLA recommendation,
customer communication preferences, metadata extraction, and acknowledgement
safety failure modes.

Return only structured output matching the requested schema.

Each generated case must include:
- id
- source = synthetic
- scenario_type
- complaint_document
- metadata
- expected_category
- expected_severity
- expected_routing
- expected_sla
- must_detect
- must_not_detect
- customer_preferences

The complaint_document is the raw input that will go to the triage LLM. It must
use this exact shape:

**Channel:** ...
**Received:** ...
**Customer ID:** ...
optional header fields such as Subject, Thread context, Agent, Duration, Note

```
customer complaint body or transcript
```

Metadata must duplicate the header values exactly where present. Missing header
values must be null.

Allowed categories:
- service_error
- financial_hardship
- responsible_lending
- collections
- fees_charges
- fraud_or_identity
- unclear_or_other

Allowed severity values:
- low
- medium
- high
- critical

Allowed routing values:
- frontline_complaints
- hardship_team
- responsible_lending_specialist
- collections_escalation
- vulnerable_customer_team
- legal_compliance_review

Use the seed guidance:
- A service complaint can mention wrong staff advice, failed direct debit
  changes, missed payments, fees, and credit-file concern without being
  hardship or responsible lending.
- A subtle hardship case may be current on payments but disclose reduced
  income, relationship breakdown, dependent children, sleep distress, and a
  request to pause or reduce repayments.
- A responsible lending case may mention a financial counsellor, unaffordable
  loan, casual income, job loss, arrears, collections contact, dependent child,
  responsible lending obligations, and AFCA escalation risk.

When reference_sample_cases_jsonl is provided in the user message, treat it as
a fixed seed knowledge base. Use it to learn the expected document shape,
realistic style, metadata duplication, and label conventions. Do not copy the
seed complaints or reuse their customer IDs. Generate new synthetic cases.

Cover shapes beyond the seeds:
- very short complaints with minimal context
- vague angry rants
- complaints about the wrong company or product
- multi-issue complaints where the headline is not the most important signal
- routine-looking complaints that hide serious hardship or safety risk
- serious-looking complaints that are routine
- poor English or hard-to-parse writing
- sarcasm
- threats, abuse, or self-harm signals
- wrong company or wrong product
- contradictory information
- routine low-risk app or service issues

Use a coverage-matrix approach when coverage_matrix is true. Do not generate a
set of generic random complaints. Spread cases across realistic failure modes:

| Scenario type | Purpose | Expected severity |
|---|---|---|
| very_short_complaint | Minimal context handling | medium |
| vague_angry_rant | Uncertainty and over-classification | medium |
| wrong_company_or_product | Irrelevant complaint detection | low |
| hidden_hardship_in_fee_complaint | Subtle vulnerability detection | high |
| multi_issue_complaint | Prioritisation across competing signals | high |
| esl_style_writing | Robust parsing | medium |
| sarcastic_complaint | Tone versus actual risk | medium |
| fraud_or_identity_theft | High-risk routing | critical |
| self_harm_signal | Safety-critical escalation | critical |
| abusive_or_threatening_customer | Staff safety and hardship separation | high |
| contradictory_complaint | Ambiguity handling | medium |
| routine_app_bug | Avoiding over-escalation | low |

Important quality rules:
- Every signal required for the expected labels must be present in the
  complaint_document itself.
- Do not require external account lookup, policy lookup, or real regulations.
- Keep cases synthetic and avoid real personal data.
- Make expected labels defensible from the text.
- expected_sla must align with expected_severity:
  low/medium -> standard_acknowledgement
  high -> same_day_acknowledgement
  critical -> urgent_review
- customer_preferences should include explicit preferences only, such as
  prefers_message_or_no_phone_contact or prefers_in_app_message.
- Do not overuse one scenario shape or one category unless the request asks for
  that focus.
- The number of cases must match the requested count.
- Include a concise generation_notes string explaining the coverage-matrix
  choices and any request-specific focus.
""".strip()
