# Agent Beta source references — 2026-09-19

- Full frontend suite: 55 files / 460 tests passed (`npm test -- --run`).
- Browser: all five cases in `tests/e2e/test_agent_comparison_frontend.py` passed.
  Three live/review cases at 1440 px light, 390 px dark and 320 px light passed
  on the first run; the two paper-citation cases at 1280/390 px passed after
  correcting the fixture to use the real bookmark-opening path. The initial
  fixture bypassed leaving the empty-chat screen; no product layout change was needed.
- Browser checks cover live, saved, archived and comparison answer references,
  the shared source preview on keyboard focus, matching source lists, preserved
  Markdown, no page errors and no horizontal overflow. Providers and auth are
  mocked; no paid model calls.
- Frontend build succeeded (`npm run build`); all 8 build contract tests passed
  (`tests/test_frontend_build.py`).
- Both screenshots visually inspected: the paper names retain their text,
  the printed URLs are replaced by raised numbers and the mobile text wraps normally.

Screenshots: `agent-paper-citations-1280.png` and `agent-paper-citations-390.png`.
