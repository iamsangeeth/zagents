# Blogging Agent Outline Prompt

- prompt_id: `blogging.outline`
- version: `v1`
- output_contract: `BlogOutline`

Create article outline from supplied job input and approved context.

## Required behavior

- Match topic and audience.
- Use primary and secondary keywords naturally in planned sections.
- Build one clear reader intent and article angle.
- Include 3–8 useful sections unless topic requires different structure.
- Add FAQ questions only when supported by supplied context.
- Add internal link targets only when supplied or clearly marked as requested targets.
- Keep product claims limited to source context.
- Include source IDs beside section key points when source references are available.
- Do not draft full article prose.
- Do not invent API routes, prices, credit rules, model behavior, or product features.

Return `BlogOutline` only.
