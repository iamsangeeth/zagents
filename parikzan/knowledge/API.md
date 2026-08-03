# API Documentation

Base: `/api`. Auth via NextAuth session cookie (JWT strategy) unless noted. Unauthed → `401 { "error": "Unauthorized" }`.

## Auth

### `POST /api/register`
Create account (email/password).
```json
// req
{ "name": "string?", "email": "string", "password": "string" }
// res 200
{ "message": "User created successfully", "user": { "id", "name", "email" } }
```
New user gets 3 credits. 400 if email exists or missing fields.

### `GET|POST /api/auth/[...nextauth]`
NextAuth handler. Providers: Google OAuth, Credentials (email+password, bcrypt).

## Quiz

### `GET /api/quiz`
List current user's quizzes w/ questions, attempt count, last attempt. Auth required.

### `POST /api/quiz/generate`
Generate quiz. Auth required. Costs 1 credit. `multipart/form-data`:
- `prompt` (string, min 10 chars)
- `difficulty` (`EASY`|`MEDIUM`|`HARD`)
- `numberOfQuestions` (1–50)
- `files` (0+ files: txt/json/csv/xlsx/xls/docx/pdf/image)

Res 200: created `Quiz` w/ `questions[]` (includes correctAnswer/explanation, this is owner-side response).
Errors: 401 unauth, 402 insufficient credits, 400 invalid input, 500 AI/parse failure.

### `GET /api/quiz/[id]`
Public-ish (no auth check in code) fetch quiz for taking — `questions[]` returned WITHOUT `correctAnswer`. 404 if not found.

### `POST /api/quiz/[id]/submit`
Submit answers. Auth required.
```json
// req
{ "answers": { "<questionId>": 0 } }
```
Server scores against stored `correctAnswer`, creates `QuizAttempt` + `Answer` rows. Res includes full quiz w/ correct answers + explanations for review.

### `POST /api/quiz/[id]/regenerate`
Regenerate questions for existing quiz. Auth required. Costs 1 credit.
```json
{ "prompt": "string", "difficulty": "EASY|MEDIUM|HARD", "numberOfQuestions": 10 }
```
Deletes old questions, creates new (Groq only, no file support). Res: `{ "success": true }`.

### `GET /api/quiz/[id]/analytics`
Auth required (must be quiz owner via userId match). Returns quiz + all attempts + latest attempt w/ answer breakdown. 404 if no attempts yet.

## Credits

### `GET /api/user/credits`
Auth required. Res: `{ "credits": number }`.

### `POST /api/credits/create-order`
Auth required. Creates Razorpay order + `PENDING` purchase record.
```json
{ "credits": 10, "amount": 5, "transactionFee": 0.45, "totalAmount": 5.45 }
```
`credits` must be multiple of 10. Res: Razorpay order object.

### `POST /api/credits/verify-payment`
Auth required. Verifies Razorpay HMAC signature, marks purchase `SUCCESS`, credits user.
```json
{ "orderId": "string", "paymentId": "string", "signature": "string" }
```
400 if signature invalid. Res: `{ "success": true }`.

## Payments

### `GET /api/payments/history`
Auth required. Res: array of `CreditPurchase` records, newest first.

### `GET /api/payments/invoice?id=<purchaseId>`
Auth required. Returns printable HTML invoice for a `SUCCESS` purchase owned by caller. 404 if not found/not owned/not success.

## Admin
All require `isAdmin=true` on caller (DB-checked, not session-trusted).

### `GET /api/admin/users`
List all users: id, name, email, credits, createdAt, successful purchases.

### `POST /api/admin/update-credits`
```json
{ "userId": "string", "credits": 15 }
```
Directly sets user credit balance (no purchase record created). 400 if credits not a non-negative number.

## GraphQL

### `POST /api/graphql`
GraphQL endpoint (also accepts `GET`, likely for GraphiQL/introspection UI). Schema/resolvers not inspected here — check `src/app/api/graphql/route.ts` for query/mutation definitions if extending.

## Misc

### `GET /api/debug`
Exists in codebase — environment/debug info. **Do not expose in production**, no auth gate found.

## Error shape
Most routes: `{ "error": "message" }` w/ appropriate status (400/401/402/404/500). Some routes use shared `handleApiError` (logs + generic 500), others inline try/catch with `console.error`.
