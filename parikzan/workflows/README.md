# n8n Blogging Agent v1

Import `blogging_agent_v1.json` into n8n.

## Configure

Optional: in n8n **Settings → Variables**, create:

```text
PARIKZAN_AGENT_URL=http://127.0.0.1:8000
```

If variable unavailable, workflows fall back to `http://parikzan-api:8000` for Compose. For host-mode n8n, configure variable with `http://127.0.0.1:8000` instead.

Expected PydanticAI service routes:

```text
POST /v1/blog/jobs
POST /v1/blog/outline
POST /v1/blog/draft
POST /v1/blog/seo
POST /v1/blog/validate
POST /v1/blog/approval/request
POST /v1/blog/approval/decide
POST /v1/blog/publish
POST /v1/blog/index
```

Each stage receives accumulated JSON context and returns accumulated JSON context. Minimum fields:

```json
{
  "job_id": "uuid",
  "input": {},
  "sources": [],
  "outline": {},
  "draft": {},
  "seo": {},
  "validation": {}
}
```

## Test request

Use n8n test webhook URL:

```bash
curl -X POST 'http://localhost:5678/webhook-test/parikzan/blog' \
  -H 'content-type: application/json' \
  -d '{
    "topic": "How quiz practice improves learning",
    "audience": "students",
    "primary_keyword": "quiz practice",
    "tone": "educational",
    "target_word_count": 1200,
    "output_format": "markdown"
  }'
```

Workflow includes bounded validation revision loop:

```text
passed=true  → awaiting_approval
passed=false → revise → validate (maximum four revisions)
exhausted    → human approval only when minimum length passes; otherwise failed/regeneration required
```

`Generate Draft` and `Revise Draft` retry transient HTTP failures up to 3 times with 5-second waits. These retries do not increase the two-revision quality limit.

Approval and publishing remain separate tasks.

## Approval UI

Import `blogging_approval_v1.json` as separate workflow and activate it. n8n Form Trigger provides approval form URL. Reviewer submits job ID, `approve` or `reject`, email, and feedback. Only approved decisions reach `/v1/blog/publish` and `/v1/blog/index`; reject path never publishes.

## Start Pydantic AI runtime

Run service from project root:

```bash
QDRANT_URL=http://127.0.0.1:6333 uv run uvicorn parikzan.api:app --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Set n8n variable `PARIKZAN_AGENT_URL` to reachable runtime URL. `/v1/blog/index` returns `indexed=false` with `index_error` when Qdrant unavailable; Markdown publication remains visible and retryable.

## Daily schedule

Main workflow keeps manual webhook trigger and adds scheduled trigger:

```text
Timezone: Asia/Kolkata
Cron: 0 8 * * *
```

Scheduled path:

```text
Schedule Daily Blog
→ Select Random Blog Topic
→ Create Blog Job
→ outline → draft → SEO → validate
```

`Select Random Blog Topic` randomly selects one curated topic from five pools: learning, self-study, competitive examinations, self-evaluation, and teacher question-paper creation. It adds audience, keyword, tone, CTA, locale, word count, and Markdown format. Manual webhook path remains available for custom topics.
