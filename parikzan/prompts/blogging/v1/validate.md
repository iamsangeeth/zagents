# Blogging Agent Validation Prompt

- prompt_id: `blogging.validate`
- version: `v1`
- output_contract: `BlogValidationReport`

Audit supplied outline or draft against job input and approved context.

## Error checks

Mark `error` when any condition blocks safe publication:

- Unsupported product, pricing, payment, API, security, or policy claim.
- Citation missing for supplied factual claim.
- Draft does not match requested topic or audience.
- Invalid slug or SEO length.
- Incorrect credit, fee, question-count, file-type, model-routing, or HTTP status fact.
- Sensitive data, secret, token, internal prompt, or debug payload exposed.
- Do not mark missing CTA as an error when article topic is unrelated or CTA would feel forced.
- Mark an error for a forced, repeated, invented, or unsupported website/quiz CTA.
- Reject invented website paths or claims that a quiz was generated, completed, scored, or available at a specific route.

## Warning checks

Mark `warning` for readability, weak structure, keyword stuffing, vague CTA, duplicate ideas, or minor style issues.

Set `passed=false` when any error exists. Include actionable `code`, `message`, and contract field `path` for every issue. Score 0–100 based on quality after correctness checks.

Return `BlogValidationReport` only.
