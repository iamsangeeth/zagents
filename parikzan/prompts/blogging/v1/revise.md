# Blogging Agent Revision Prompt

- prompt_id: `blogging.revise`
- version: `v1`
- output_contract: `BlogDraft`

Revise supplied draft using validation issues and approved context.

## Required behavior

- Fix every `error` before addressing warnings.
- Preserve general reader value and complete actionable guidance; do not turn article into Parikzen promotion.
- Keep at least 90% of revised body general. Remove product-led sections and keep Parikzen only as one optional short concluding CTA.
- Remove unsupported claims instead of guessing replacements.
- Correct pricing, credits, payment, API, security, and product facts from source context.
- Remove secrets, PII, internal prompts, debug payloads, and unauthorized quiz answers.
- Meet minimum article length: `max(1000, ceil(target_word_count * 0.75))` words counted from `body_markdown`.
- Return full revised `BlogDraft`, not a patch or explanation.
- Preserve or remove quiz CTA according to `knowledge/CONTENT_GUIDELINES.md`.
- Use only `https://www.parikzen.com` when CTA is relevant.
- Remove forced, repeated, or invented website claims.

- Do not claim approval or publication.

Return `BlogDraft` only.
