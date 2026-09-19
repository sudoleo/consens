# Agent comparisons — validation, 2026-09-19

Implemented in the existing `main` checkout. No live provider calls or production
database writes were made for these checks.

## Automated checks actually run

- Full isolated backend suite: **2398 passed** (14 existing dependency warnings).
  This includes existing Consensus, judge, streaming, persistence, cost and Agent
  regressions. One additional recovery test was added afterwards.
- Latest targeted backend check after the final route/orchestration cleanup:
  `tests/test_agent_comparison.py tests/test_agent_runs.py
  tests/test_agent_delegation.py`: **62 passed**.
- Full frontend suite: **433 passed** across 52 files, with build freshness check.
  After the final layout and stale-review fixes, the affected Agent chat tests
  (**25 passed**) and Agent review tests (**2 passed**) were repeated.
- Agent comparison + existing Agent chat Playwright suites: **18 passed**.
- Existing delegation responsive Playwright suite: **5 passed**.
- Final comparison Playwright rerun after renderer/style changes: **3 passed**.
- Final frontend build succeeded; `build:check` and the Python build contract
  (**8 passed**) succeeded. Prior released assets are retained by the build's
  normal rollover policy rather than replaced by intermediate development builds.
- `git diff --check`: clean.

The comparison backend tests exercise the real shared Differences/Coverage
prompt/parser flow with deterministic provider replies: multiple comparison
bases (including narrated tool calls), neutral isolated context and sources, exact answer versions, bounded
revision, cross-family judges, partial/failing results, mandatory review,
disconnect settlement, atomic quota admission, unknown usage, UTC rollover and
read-only saved-answer recovery.

## Visual and interaction checks

The six sibling PNGs show the built app at 1440 px (light), 390 px (dark) and
320 px (light), before sending and after a checked answer. Visually inspected
the responsive composer and review details; tested keyboard operation,
individual-answer disclosure, marker rendering, persisted projection, console
errors and horizontal overflow. Layout assertions also protect the text input
width and prevent chat model/quota labels collapsing into narrow columns.

## Not executable in this environment

The real Firestore transaction suite was attempted through
`dev.ps1 check browser -TestPath tests/e2e/test_agent_transactions.py`, but could
not start because **Java 21+ is missing**. The new emulator test is included;
in-memory atomic quota/idempotence tests passed. Deterministic browser tests do
not need the emulator.

Paid provider probes across all supported chat/comparison/reasoning combinations
were not run. Provider behavior and production Firestore contention therefore
remain outside the validation performed here.
