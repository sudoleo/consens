# Source-check result navigation

Verified 2026-09-13 using fixture answers in the real app shell and the local
Firestore test emulator. No live model calls or production data.

- 111 targeted JavaScript tests passed (source checks, reader, footer, bookmarks,
  and polling).
- 18 asset/build tests passed; `npm run build` and the build freshness check passed.
- 6 browser tests passed at 1440 px and 390 px. They cover checked and excluded
  explanations, keyboard focus, visible reasons, cue expiration, repeated jumps,
  and Reduced Motion with Forced Colors.
- Screenshots show the temporary cue in light/dark mode and excluded checks.
  At 390 px the existing footer hides the status button, so
  the narrow-reader check invokes the same navigation entry point directly.

The cue is limited to the source-check section and fades after 2.8 seconds.
Unfinished/excluded results take precedence when several result cards exist.
Legacy checks or snapshots without a rendered contradiction result open the
Sources report. Polling preserves the remaining cue duration; a different
answer or explicit clear removes it.
