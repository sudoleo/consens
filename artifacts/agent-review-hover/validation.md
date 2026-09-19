# Agent review status and desktop hover — 2026-09-19

## Verified causes

- Read the affected saved run in the user's local app. GPT-5.6 Luna's activity
  records a provider rate limit with a 30-second wait. Five comparison answers,
  the coverage judge and the differences judge completed. No additional paid
  request was made to inspect or reopen this run.
- The generic partial label conflated a missing model answer with failed checks.
  The refreshed saved run now reads `Comparison checked · 1 model unavailable`,
  `Answers 5`, and `5 of 6 models returned complete answers` in Review. Both
  checks are complete; the source report says no checkable contradictions.
- A browser regression reproduced the hover failure before the fix: mouseenter
  followed by a trailing scroll cleared the preview timer permanently while
  the pointer remained on the green passage. The preview now resumes after
  scrolling settles and remains inside the viewport.

## Validation

- Agent backend suite: 303 passed, including rate-limited comparison with two
  successful remaining answers and real shared judges; review bindings preserved.
- Complete frontend suite: 476 passed; build freshness passed.
- Agent comparison browser suite: 6 passed, including desktop/mobile layouts,
  citation links, keyboard controls, saved/history views and the new real-mouse
  hover/scroll/reprojection regression with formatted green passages.
- Additional frontend regression: touch creates no hover preview; a mouse
  connected after rendering enables it without rerendering the answer.

The provider's rate limit remains an external condition; the change reports it
accurately rather than treating missing model evidence as full success. New runs
persist the safe reason directly with the comparison. Older runs retain their
detailed reason in Agent activity. No production deployment was performed.
