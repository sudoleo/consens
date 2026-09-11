While agent-mode models stream, each row now shows the number of characters actually received (for example, `1,234 chars`), then freezes its completion time. Waiting, reasoning, failed, skipped, and canceled requests have distinct labels. Counts use the projected raw answer rather than rendered loading text or Markdown controls, and reset with the visible run.

The active phase uses three gently animated strokes and a text shimmer. Model bars stay visible; next steps move below them with `Next — … → …` wording. Reduced Motion disables animation, and only phase/completion changes enter the screen-reader live region. The existing skip action remains keyboard accessible.

Validation:
- 255 JavaScript tests passed, including raw counts, Unicode, state transitions, run switching and announcement deduplication.
- Full Python run: 1,920 passed, one stale CSS cache reference found and fixed; all 35 affected asset/progress tests then passed.
- 10 Chromium component checks passed at 320/390/768/1280 px, in Light/Dark, with phase handoff, Reduced Motion, keyboard skip and UTF-8 assertions. Screenshots inspected.
- Reader PR #1 integrated before final build and browser/asset validation; generated bundles and codebase/smoke documentation updated.
