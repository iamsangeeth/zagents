# Parikzen — Product Documentation

## What it is
AI quiz generator. User give prompt or file → AI make multiple choice quiz → user take quiz → score tracked.

## Core Features

**Quiz generation**
- Input: text prompt, or uploaded file, or both.
- Difficulty: EASY / MEDIUM / HARD.
- Question count: 1–50.
- Engine pick auto:
  - No files → Groq (`llama-3.1-8b-instant`), cheapest.
  - Files parsable in-browser (txt/json/csv/xlsx/xls/docx) → parse locally, feed text to Groq.
  - Files not parsable (PDF, images) → Gemini (`gemini-1.5-flash`), handles raw file directly.
- AI response retried up to 2x on bad JSON (Groq path), temperature drop each retry.
- Duplicate answer options deduped, options shuffled, correct-answer index remapped after shuffle.
- Costs 1 credit per generation. Blocked at 0 credits (402 returned).

**Quiz regeneration**
- Regenerate questions for existing quiz (same prompt path stored, new Groq call).
- Replaces old questions (delete + recreate), costs 1 credit.

**Taking a quiz**
- Fetch quiz w/o correct answers exposed.
- Submit answers → server scores, stores `QuizAttempt` + `Answer` rows.
- Response includes correct answers + explanations for review after submit.

**Analytics**
- Per-quiz attempt history, latest attempt highlighted, answer-level breakdown w/ correct/incorrect + explanation.

**Dashboard**
- List user's quizzes, last attempt status, attempt count.

**Credits & payments**
- New user: 3 free credits on signup.
- Buy more via Razorpay checkout (see pricing doc).
- Payment history + printable HTML invoice per purchase.

**Admin**
- Admin flag (`isAdmin`) gates `/api/admin/*`.
- List all users w/ credit balance + successful purchase history.
- Manually set any user's credit balance.

**Auth**
- Google OAuth + email/password (bcrypt hashed, credentials provider).
- JWT session strategy. Session carries `isAdmin` + `credits` (refreshed on login, not live).

## Data model (Prisma / Postgres)
- `User` — credits, isAdmin, auth relations.
- `Quiz` — belongs to user, has questions, difficulty enum (EASY/MEDIUM/HARD).
- `Question` — options[], correctAnswer index, explanation.
- `QuizAttempt` — score, totalQuestions, per-user per-quiz.
- `Answer` — per-question answer in an attempt, isCorrect flag.
- `CreditPurchase` — credits, amount, fee, total, Razorpay orderId/paymentId, status enum (PENDING/SUCCESS/FAILED).

## Supported file types
`txt`, `json`, `csv`, `xlsx`, `xls`, `docx` parsed client-side (mammoth/xlsx/papaparse). Anything else (PDF, images) routed to Gemini directly — no local text extraction.

## Tech stack
Next.js 14 App Router, TypeScript, Prisma/Postgres, NextAuth, Ant Design + Tailwind, Zod validation, Groq SDK + Google Generative AI SDK, Razorpay.

## Known gaps (found in code, not fixed, flag for you)
- Debug console.log leaking `RAZOR_KEY_ID`/secret presence and admin-check internals to server logs — strip before prod.
- `/api/debug` route exists — check no PII/secret leak, restrict or remove for prod.
- Session `credits`/`isAdmin` set at JWT issuance only — stale until re-login/token refresh. Client-critical checks should hit DB, not trust session claim for admin gating on sensitive ops (admin routes do re-check DB — good. But e.g. UI credit display can lag actual value).
