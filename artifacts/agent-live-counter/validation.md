# Agent sidebar live counters — 2026-09-19

- Final backend check: 62 passed across progress, delegation, comparisons,
  contradiction tools and continuation. Covers numeric snapshots, Unicode
  character counts, throttling, usage aggregation across worker steps, transient
  coalescing without filling the durable-event queue, accounting and cancellation.
- Additional run/build checks: 56 passed across Agent runs, continuation and
  frontend build contracts (continuation overlaps the final check).
- Frontend: 55 passed across Agent sidebar, chat lifecycle and SSE completion.
- Browser: 8 passed in `test_agent_delegation_frontend.py`. The three new cases
  use an open ReadableStream through the real SSE parser at 1440 px light,
  390 px dark and 320 px light. They verify pending shimmer, increasing character
  counts, provider token updates, completion, Reduced Motion and Forced Colors.
  The existing five sidebar/detail/saved-view cases also pass.
- `npm run build` and `git diff --check` pass. No paid model calls.
- Screenshots at all three new widths visually inspected; the counter fits
  the existing metadata row without horizontal overflow.

Screenshots: `agent-live-counter-1440.png`, `agent-live-counter-390.png`,
`agent-live-counter-320.png`.
