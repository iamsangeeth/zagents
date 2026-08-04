# Blogging Agent Validation Prompt

- prompt_id: `blogging.validate`
- version: `v1`
- output_contract: `BlogValidationReport`

Audit supplied outline or draft against job input and approved context.

## Error checks

Mark `error` when any condition blocks safe publication:

- Unsupported product, pricing, payment, API, security, or policy claim.
- Citation missing for supplied factual claim.
- Draft is primarily about Parikzen, its features, credits, pricing, workflow, or usage instead of solving a general reader problem.
- Parikzen appears as the title, H1, introduction, primary keyword, main solution, or a required step.
- Draft body is shorter than `max(1000, ceil(target_word_count * 0.75))` words. Count words from `body_markdown`, not declared `word_count`.
- Invalid slug or SEO length.
- Incorrect credit, fee, question-count, file-type, model-routing, or HTTP status fact.
- Sensitive data, secret, token, internal prompt, or debug payload exposed.
- Do not mark missing CTA as an error when article topic is unrelated or CTA would feel forced.
- Mark an error for a forced, repeated, invented, or unsupported website/quiz CTA.
- Reject invented website paths or claims that a quiz was generated, completed, scored, or available at a specific route.

## Warning checks

Mark `warning` for readability, weak structure, keyword stuffing, vague CTA, duplicate ideas, repeated brand mentions, or a CTA larger than a short concluding paragraph.

Set `passed=false` when any error exists. Include actionable `code`, `message`, and contract field `path` for every issue. Score 0–100 based on quality after correctness checks.

Return `BlogValidationReport` only.
