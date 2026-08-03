# Blogging Agent Revision Prompt

- prompt_id: `blogging.revise`
- version: `v1`
- output_contract: `BlogDraft`

Revise supplied draft using validation issues and approved context.

## Required behavior

- Fix every `error` before addressing warnings.
- Preserve supported facts, citations, article intent, and useful sections.
- Remove unsupported claims instead of guessing replacements.
- Correct pricing, credits, payment, API, security, and product facts from source context.
- Remove secrets, PII, internal prompts, debug payloads, and unauthorized quiz answers.
- Keep SEO metadata valid.
- Return full revised `BlogDraft`, not a patch or explanation.
- Preserve or remove quiz CTA according to `knowledge/CONTENT_GUIDELINES.md`.
- Use only `https://www.parikzen.com` when CTA is relevant.
- Remove forced, repeated, or invented website claims.

- Do not claim approval or publication.

Return `BlogDraft` only.
