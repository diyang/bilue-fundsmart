# Synthetic Data Generation Notes

Generated using a coverage-matrix approach based on the seed complaints and synthetic test case generation spec.

## Generator Notes

Generated 10 synthetic FundSmart cases using the seed document shape and label conventions without reusing seed IDs or text. Coverage-matrix selections emphasise minimal context, abuse/threat handling, wrong-product detection, hidden hardship, multi-issue prioritisation, ESL parsing, sarcasm, identity theft, self-harm escalation, and routine app/service issues. Severity-to-SLA alignment is maintained: low/medium use standard acknowledgement, high uses same-day acknowledgement, and critical uses urgent review.

## Generated Coverage

- SYN-GEN-001: very_short_complaint (collections, medium)
- SYN-GEN-002: abusive_or_threatening_customer (collections, high)
- SYN-GEN-003: wrong_company_or_product (unclear_or_other, low)
- SYN-GEN-004: hidden_hardship_in_fee_complaint (financial_hardship, high)
- SYN-GEN-005: multi_issue_complaint (responsible_lending, high)
- SYN-GEN-006: esl_style_writing (service_error, medium)
- SYN-GEN-007: sarcastic_complaint (service_error, medium)
- SYN-GEN-008: fraud_or_identity_theft (fraud_or_identity, critical)
- SYN-GEN-009: self_harm_signal (financial_hardship, critical)
- SYN-GEN-010: routine_app_bug (service_error, low)

