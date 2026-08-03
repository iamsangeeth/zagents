# Pricing & FAQ

## Pricing (credit packs)

| Credits | Price | Per-credit | Transaction fee | Total charged |
|---|---|---|---|---|
| 10 | $5 | $0.50 | 3% + $0.30 = $0.45 | $5.45 |
| 20 | $9 (Popular) | $0.45 | 3% + $0.30 = $0.57 | $9.57 |
| 50 | $20 | $0.40 | 3% + $0.30 = $0.90 | $20.90 |
| 100 | $35 | $0.35 | 3% + $0.30 = $1.35 | $36.35 |

Fee formula: `fee = price * 0.03 + 0.30`. Charged on top of listed price, shown at checkout before pay.

1 credit = 1 quiz generation (also 1 regeneration). New signup gets 3 credits free.

Currency note: checkout currency hardcoded `USD` in Razorpay order, prices shown as `$`.

## FAQ

**Do credits expire?**
No. Stated explicitly in purchase UI.

**What happens at 0 credits?**
Generate/regenerate blocked, API returns 402 Insufficient credits. Buy more or wait for... nothing — no free refill besides signup bonus. (No subscription/auto-refill exists in code.)

**How is quiz generated?**
Groq for text-only/parsable-file input (fast, cheap). Gemini for PDFs/images (needs vision-capable model). Auto-selected, not user-chosen.

**Which file types can I upload?**
txt, json, csv, xlsx, xls, docx (parsed locally) or PDF/images (sent to Gemini as-is). Other types rejected.

**How many questions can a quiz have?**
1 to 50, validated server-side (Zod).

**Payment provider?**
Razorpay. Card/method captured by Razorpay, invoice shows last-4 if card used.

**Refunds?**
Not implemented in code — no refund endpoint/logic exists. Handle manually via admin credit adjustment or Razorpay dashboard if needed.

**Can I see past payments / get invoice?**
Yes — `/payments` page lists history, invoice fetchable per successful payment (printable HTML, "Download PDF" = browser print).

**Is there a free tier / trial?**
3 free credits at registration is the only trial mechanism.

**Admin override credits?**
Yes, admin can set any user's credit balance directly (no audit trail beyond DB row — no purchase record created for manual adjustment).

**Data retention for quizzes/attempts?**
No deletion/expiry logic found — quizzes, attempts, answers persist indefinitely, cascade-deleted only if user account deleted.
