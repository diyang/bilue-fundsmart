# Synthetic Complaint Test Data Generation Spec

## Purpose

This document defines how to generate additional synthetic test cases for the Bilue AI Engineer take-home exercise.

The goal is to create a representative synthetic evaluation set for a complaint triage and acknowledgement drafting assistant. The test cases should assess whether the system can correctly identify:

- Complaint category
- Severity
- Vulnerability signals
- Regulatory or escalation flags
- Recommended routing
- SLA recommendation
- Customer communication preferences
- Safe and appropriate acknowledgement drafting

The synthetic cases should be self-contained. Each complaint must include enough information inside the message itself for the system to classify and route it without relying on external customer history, contracts, or regulatory documents.

---

## Required Output Files

Generate the following files:

```text
data/
├── synthetic_complaints.jsonl
└── gold_labels.jsonl
```

Optional but recommended:

```text
data/
└── synthetic_generation_notes.md
```

---

## Synthetic Data Design Approach

Do not randomly generate ten generic complaints.

Instead, use a coverage-matrix approach. The three seed complaints already cover:

1. A service complaint without vulnerability or regulatory flags.
2. A subtle hardship case with vulnerability signals.
3. A high-severity responsible lending complaint with AFCA escalation risk.

The additional synthetic cases should cover missing edge cases and failure modes, including:

- Very short complaints with minimal context
- Vague emotional rants
- Complaints about the wrong company or product
- Hidden hardship inside an apparently routine fee complaint
- Multi-issue complaints
- Customers whose first language may not be English
- Sarcasm or indirect language
- Fraud or identity theft
- Self-harm signals
- Abusive or threatening language
- Contradictory customer statements
- Routine low-risk app or service issues

---

## Synthetic Test Case Coverage Matrix

Create at least 10 additional synthetic complaints. This spec provides 12.

| ID | Scenario Type | Purpose | Expected Severity |
|---|---|---|---|
| SYN-001 | Very short complaint | Tests minimal context handling | Medium |
| SYN-002 | Vague angry rant | Tests uncertainty and over-classification | Medium |
| SYN-003 | Wrong company/product | Tests irrelevant complaint detection | Low |
| SYN-004 | Hidden hardship in fee complaint | Tests subtle vulnerability detection | High |
| SYN-005 | Multi-issue complaint | Tests prioritisation across competing signals | High |
| SYN-006 | Poor English / ESL-style writing | Tests robust parsing | Medium |
| SYN-007 | Sarcastic complaint | Tests tone versus actual risk | Medium |
| SYN-008 | Fraud / identity theft | Tests high-risk routing | Critical |
| SYN-009 | Self-harm signal | Tests safety-critical escalation | Critical |
| SYN-010 | Abusive or threatening customer | Tests staff safety and hardship separation | High |
| SYN-011 | Contradictory complaint | Tests ambiguity handling | Medium |
| SYN-012 | Routine app bug | Tests avoiding over-escalation | Low |

---

## File 1: `data/synthetic_complaints.jsonl`

Create a JSONL file where each line is one complaint object.

Each object should follow this structure:

```json
{
  "id": "SYN-001",
  "channel": "email | in_app | call_transcript",
  "received": "2026-04-18 09:12 AEST",
  "customer_id": "CUST-60001",
  "subject": "Optional subject line",
  "message": "Complaint text"
}
```

Use the following synthetic complaints.

```jsonl
{"id":"SYN-001","channel":"in_app","received":"2026-04-18 09:12 AEST","customer_id":"CUST-60001","message":"You charged me twice this month. Fix it and refund me."}
{"id":"SYN-002","channel":"email","received":"2026-04-18 10:05 AEST","customer_id":"CUST-60002","subject":"Absolutely useless","message":"I am sick of this company. Every time I try to get help, nobody knows what they are doing. Your app is terrible, your staff are useless, and I want someone senior to look at my account immediately."}
{"id":"SYN-003","channel":"email","received":"2026-04-18 11:21 AEST","customer_id":"UNKNOWN","subject":"My insurance claim has not been paid","message":"I lodged a car insurance claim three weeks ago and nobody has paid me. I do not have a loan with FundSmart, but this is the only email address I could find. Please fix my insurance claim."}
{"id":"SYN-004","channel":"in_app","received":"2026-04-18 13:44 AEST","customer_id":"CUST-60004","message":"Why have I been charged another late fee? I know the payment was late but I lost shifts last month and I had to choose between paying rent and paying this loan. I can probably catch up next month but right now I cannot afford extra fees."}
{"id":"SYN-005","channel":"email","received":"2026-04-18 15:02 AEST","customer_id":"CUST-60005","subject":"Complaint about collections calls and payment arrangement","message":"I made a payment arrangement with your team last week to pay $150 a fortnight until I am back at work. Since then I have received four collections calls and two texts saying I am overdue. I am recovering from surgery and cannot take calls during the day. I want the calls stopped and the arrangement honoured."}
{"id":"SYN-006","channel":"in_app","received":"2026-04-19 08:30 AEST","customer_id":"CUST-60006","message":"Hello I pay already loan yesterday from bank. Today app say not pay and late money charge. I no understand. Please check because I do not want bad credit. My English not good please message me here."}
{"id":"SYN-007","channel":"email","received":"2026-04-19 09:45 AEST","customer_id":"CUST-60007","subject":"Great job losing my documents","message":"Fantastic work FundSmart. I uploaded my payslips three times and your app still says you have not received them. Really impressive. Maybe the fourth time will magically work. I need this fixed because my refinance application is now delayed."}
{"id":"SYN-008","channel":"email","received":"2026-04-19 11:10 AEST","customer_id":"CUST-60008","subject":"Loan opened in my name","message":"I received an email saying I missed a repayment, but I never applied for a FundSmart loan. I think someone has used my identity. I need this investigated immediately and I do not want this affecting my credit file."}
{"id":"SYN-009","channel":"in_app","received":"2026-04-19 22:18 AEST","customer_id":"CUST-60009","message":"I cannot keep doing this. The loan, the calls, everything is too much. I feel like there is no way out and I do not know if I can keep myself safe tonight. Please stop contacting me about money."}
{"id":"SYN-010","channel":"call_transcript","received":"2026-04-20 12:02 AEST","customer_id":"CUST-60010","message":"CUSTOMER: You people are thieves. If another person from your collections team calls me, I am coming down to your office and someone is going to regret it. I have already told you I lost my job and cannot pay this month."}
{"id":"SYN-011","channel":"email","received":"2026-04-20 14:25 AEST","customer_id":"CUST-60011","subject":"Late payment mark","message":"You marked my payment as late even though I paid on time. I mean, I did pay two days after the due date, but that was because your reminder email went to spam. I want the late mark removed because this is not my fault."}
{"id":"SYN-012","channel":"in_app","received":"2026-04-20 16:40 AEST","customer_id":"CUST-60012","message":"The app keeps logging me out when I try to download my loan statement. I need the statement for my records. Please send it to me or fix the app."}
```

---

## File 2: `data/gold_labels.jsonl`

Create a JSONL file where each line contains the expected evaluation labels for one complaint.

Each object should follow this structure:

```json
{
  "id": "SYN-001",
  "expected_category": "fees_charges",
  "expected_severity": "medium",
  "expected_routing": "frontline_complaints",
  "must_detect": ["duplicate_charge", "refund_request"],
  "must_not_detect": ["hardship", "responsible_lending", "self_harm"]
}
```

Use these gold labels.

```jsonl
{"id":"SYN-001","expected_category":"fees_charges","expected_severity":"medium","expected_routing":"frontline_complaints","must_detect":["duplicate_charge","refund_request"],"must_not_detect":["hardship","responsible_lending","self_harm"]}
{"id":"SYN-002","expected_category":"unclear_or_other","expected_severity":"medium","expected_routing":"frontline_complaints","must_detect":["unclear_issue","escalation_request"],"must_not_detect":["financial_hardship","responsible_lending","AFCA","self_harm"]}
{"id":"SYN-003","expected_category":"unclear_or_other","expected_severity":"low","expected_routing":"frontline_complaints","must_detect":["wrong_company_or_product"],"must_not_detect":["loan_complaint","hardship","responsible_lending"]}
{"id":"SYN-004","expected_category":"financial_hardship","expected_severity":"high","expected_routing":"hardship_team","must_detect":["financial_hardship","reduced_income","late_fee","cannot_afford_repayment"],"must_not_detect":["responsible_lending","fraud"]}
{"id":"SYN-005","expected_category":"collections","expected_severity":"high","expected_routing":"collections_escalation","must_detect":["payment_arrangement","collections_contact","medical_vulnerability","contact_preference"],"must_not_detect":["responsible_lending","fraud"]}
{"id":"SYN-006","expected_category":"service_error","expected_severity":"medium","expected_routing":"frontline_complaints","must_detect":["payment_not_recognised","late_fee","credit_file_concern","prefers_in_app_message"],"must_not_detect":["hardship","responsible_lending","self_harm"]}
{"id":"SYN-007","expected_category":"service_error","expected_severity":"medium","expected_routing":"frontline_complaints","must_detect":["document_upload_issue","sarcasm","application_delay"],"must_not_detect":["hardship","self_harm","abuse_threat"]}
{"id":"SYN-008","expected_category":"fraud_or_identity","expected_severity":"critical","expected_routing":"legal_compliance_review","must_detect":["identity_theft","unauthorised_loan","credit_file_risk"],"must_not_detect":["routine_payment_issue","hardship"]}
{"id":"SYN-009","expected_category":"financial_hardship","expected_severity":"critical","expected_routing":"vulnerable_customer_team","must_detect":["self_harm_signal","financial_distress","collections_contact_distress"],"must_not_detect":["routine_service_error"]}
{"id":"SYN-010","expected_category":"collections","expected_severity":"high","expected_routing":"collections_escalation","must_detect":["threatening_language","job_loss","financial_hardship","collections_complaint"],"must_not_detect":["self_harm","responsible_lending"]}
{"id":"SYN-011","expected_category":"fees_charges","expected_severity":"medium","expected_routing":"frontline_complaints","must_detect":["late_payment_dispute","contradictory_information","credit_file_concern"],"must_not_detect":["hardship","responsible_lending","fraud"]}
{"id":"SYN-012","expected_category":"service_error","expected_severity":"low","expected_routing":"frontline_complaints","must_detect":["app_issue","statement_request"],"must_not_detect":["hardship","responsible_lending","AFCA","self_harm"]}
```

---

## Optional File 3: `data/synthetic_generation_notes.md`

Create a short note explaining how the synthetic data was generated.

```markdown
# Synthetic Data Generation Notes

I generated 12 additional synthetic complaints using a coverage-matrix approach rather than random generation.

The three provided seed complaints cover:
1. A routine service complaint.
2. A subtle hardship case.
3. A high-severity responsible lending and AFCA-risk case.

The additional cases were designed to expose likely triage failure modes:

- Minimal context
- Vague emotional language
- Wrong-company or wrong-product complaints
- Hidden hardship inside routine fee disputes
- Multi-issue complaints
- ESL-style language
- Sarcasm
- Fraud or identity theft
- Self-harm signals
- Threatening or abusive language
- Contradictory facts
- Routine low-risk app issues

Each synthetic case is self-contained. The triage system should be able to infer category, severity, vulnerability signals, regulatory flags, recommended routing, SLA priority, and acknowledgement requirements from the complaint text alone.

The aim is not to create a statistically representative production dataset. The aim is to create a small but diverse evaluation set that can reveal whether the prototype is robust across realistic complaint shapes and safety-critical edge cases.
```

---

## Expected Category Values

Use the following category values consistently:

```text
service_error
financial_hardship
responsible_lending
collections
fees_charges
fraud_or_identity
unclear_or_other
```

---

## Expected Severity Values

Use the following severity values consistently:

```text
low
medium
high
critical
```

---

## Expected Routing Values

Use the following routing values consistently:

```text
frontline_complaints
hardship_team
responsible_lending_specialist
collections_escalation
vulnerable_customer_team
legal_compliance_review
```

---

## Suggested Evaluation Metrics

The evaluation script should compare system outputs against the gold labels.

At minimum, implement:

```text
category_accuracy
severity_accuracy
routing_accuracy
must_detect_recall
must_not_detect_violation_rate
```

Optional but recommended:

```text
critical_case_recall
vulnerability_signal_recall
regulatory_flag_recall
acknowledgement_quality_score
```

---

## Evaluation Logic

For each complaint:

1. Run the complaint through the triage pipeline.
2. Compare predicted category with expected category.
3. Compare predicted severity with expected severity.
4. Compare predicted routing with expected routing.
5. Check whether all `must_detect` signals appear in the model output.
6. Check whether any `must_not_detect` signals were incorrectly added.
7. Save per-case results.
8. Aggregate final metrics.

Example per-case evaluation output:

```json
{
  "id": "SYN-004",
  "category_correct": true,
  "severity_correct": true,
  "routing_correct": true,
  "must_detect_recall": 0.75,
  "must_not_detect_violations": [],
  "notes": "Detected hardship and reduced income but missed late fee."
}
```

Example aggregate evaluation output:

```json
{
  "total_cases": 12,
  "category_accuracy": 0.83,
  "severity_accuracy": 0.75,
  "routing_accuracy": 0.83,
  "must_detect_recall": 0.78,
  "must_not_detect_violation_rate": 0.08
}
```

---

## Codex Task

Use this Markdown spec to generate:

1. `data/synthetic_complaints.jsonl`
2. `data/gold_labels.jsonl`
3. `data/synthetic_generation_notes.md`
4. Any necessary loader or helper functions to read these files in the evaluation pipeline.

Requirements:

- Preserve the exact IDs.
- Preserve JSONL format: one valid JSON object per line.
- Do not wrap JSONL files in arrays.
- Ensure all JSON is valid.
- Ensure category, severity, and routing values match the allowed values exactly.
- Keep complaint messages synthetic and self-contained.
