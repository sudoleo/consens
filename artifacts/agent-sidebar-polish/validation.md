# Agent sidebar polish — 2026-09-19

Implemented and validated:

- Sidebar enters smoothly; desktop chat width adjusts with it. Reduced Motion disables these transitions.
- Model rows show measured input + output tokens, with partial and unavailable usage distinguished. Reasoning/cache subtotals are not counted twice.
- Judge details render from the existing public session snapshot with no detail/message request.
- Other agent details immediately show a skeleton on first load, then reuse the message sequence cache when reopened.
- Tool mentions remain plain text. Only confirmed running tool events receive the compact call indicator.

Validation:

- 59 JavaScript tests passed (`agent-delegation`, `agent-chat`, `model-answer-reader`).
- 23 backend frontend-build/resilience/chat-session contract tests passed.
- 11 browser cases passed (sidebar, comparison review, live reasoning), including desktop, 390px/320px, light/dark, keyboard and Reduced Motion.
- Browser tests delay worker detail loading by 600ms to verify the immediate skeleton and assert no new requests on cache reuse or judge expansion.
- `npm run build` and `npm run build:check` passed.
- Screenshots use deterministic fixtures; no paid provider calls were made.

Retained screenshots show the judge layout on desktop/mobile and plain tool mentions versus a confirmed active call.
