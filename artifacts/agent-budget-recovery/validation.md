# Agent budget, recovery and database usage — 2026-09-19

Verified behavior:

- Recovery is a deduplicated action on the same run/bookmark identity. It never starts a paid call. Known terminal failures without a saved answer hide the recovery link; unknown transport outcomes can still be checked.
- Current and historical question bubbles omit the redundant Question label.
- The sidebar percentage is based on measured consumption. Reserving/releasing tokens alone does not change it. Available and reserved tokens remain visible in the quota panel; older config generations cannot overwrite a reset.
- Live session events suppress redundant list polling. A visible tab repairs a quiet stream after 10 seconds, and completion gets one final refresh. A late poll cannot revive a finished run. The backend reuses the receipt snapshot for the lease check and response.
- Web Search remains available after reasoning when admission allows it. Skipped searches are identified as a budget-reservation limit, with no relaxation of paid-call safeguards.
- Admin → Limits independently saves the daily token limit and resets all Agent accounts. Revisions prevent duplicate/stale resets. The reset rotates a global generation without scanning users; in-flight receipts retain their original ledger and unused review holds migrate safely.

Validation:

- 97 backend/contract tests passed, including concurrent reset, authorization, strict validation, cache, failed writes, in-flight settlement and review-hold migration.
- 68 JavaScript tests passed, including recovery deduplication, stale account/config responses, stable percentages, quiet-stream polling and admin save/reset.
- 15 browser cases passed: 8 quota/recovery/sidebar cases and 7 chat-history/admin cases. The first run exposed old assertions for the removed Question label and a test-only route callback error; both test fixtures were corrected and all 7 affected cases passed on rerun.
- Desktop, 390px/320px, dark/light chat, keyboard and reduced-motion paths checked. Admin screenshots show isolated fixture values, not production settings.
- `npm run build`, `npm run build:check`, and diff whitespace checks passed.
- All browser/API tests use isolated local fixtures. No production quotas were reset and no paid model calls were made.
