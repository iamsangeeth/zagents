# Blogging Agent SEO Prompt

- prompt_id: `blogging.seo`
- version: `v1`
- output_contract: `SEOData`

Generate SEO metadata for supplied approved article draft.

## Requirements

- `meta_title`: 10–60 characters.
- `meta_description`: 50–160 characters.
- `slug`: lowercase ASCII words separated by single hyphens.
- Use primary keyword when natural.
- Use secondary keywords only when relevant.
- Avoid keyword stuffing, unsupported superlatives, and unverifiable guarantees.
- Do not add product features or pricing absent from source context.
- Keep tags concise and relevant.

Return `SEOData` only.
