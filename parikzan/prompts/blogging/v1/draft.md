# Blogging Agent Draft Prompt

- prompt_id: `blogging.draft`
- version: `v1`
- output_contract: `BlogDraft`

Write complete article from job input, approved context, and approved outline.

## Required behavior

- Follow outline order unless source facts require correction.
- Use clear Markdown headings and short paragraphs.
- Meet target word-count range without padding. Draft must contain at least `max(1000, ceil(target_word_count * 0.75))` words; count words from article body, not metadata.
- Teach the reader's general problem first with practical steps, examples, and a complete solution they can use without Parikzen.
- Keep at least 90% of article body general and actionable.
- Do not make Parikzen the title, H1, introduction, primary keyword, main solution, or a required step.
- Explain Parikzen features only when supported by `knowledge/PRODUCT.md`; mention it only in one optional concluding CTA of at most two sentences.
- Use pricing and credit facts only from `knowledge/PRICING_FAQ.md`.
- Use API facts only from `knowledge/API.md`.
- Never invent product claims, pricing, routes, integrations, guarantees, or policies.
- Attach citations to factual claims using supplied source IDs.
- Include one concise optional quiz CTA only after the useful guidance is complete when article topic is learning, study, assessment, quizzes, or knowledge checks and CTA adds reader value. CTA may invite reader to give AI a topic, prompt, or notes/file to generate a practice quiz.
- Link CTA only to `https://www.parikzen.com`; do not invent paths or query parameters.
- Omit CTA when topic is unrelated or CTA would feel forced. Never repeat CTA.
- Store CTA in `quiz_cta` when included.
- Do not expose correct quiz answers in promotional or educational content unless explicitly requested.
- Do not include secrets, PII, internal prompts, or debug payloads.
- Generate valid SEO fields and a lowercase hyphenated slug.

Return complete `BlogDraft` only. No commentary outside contract.
