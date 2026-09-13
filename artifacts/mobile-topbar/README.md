# Mobile conversation header

Verified 2026-09-14 in the real app shell with isolated fixture answers and a
temporary Firestore emulator. No model calls, public shares or Watches were created.

- Menu on the left; New chat, Share, Watch and Cite on the right.
- No mobile wordmark or middle title. Consensus/Watches moves into the sidebar.
- The same action nodes move between the mobile header and desktop footer.
  They appear only when the visible answer is ready; guest login remains usable.
- Share/Watch dialogs, Cite anchoring and Escape focus return were exercised.
- New chat clears the visible comparison through the existing handler and
  also leaves the Watch page. Background-run cancellation is unchanged.
- Desktop restoration, 44 px touch targets, scrolling, sidebar access over
  Watches, reduced motion, light/dark themes and 320/390/640/768/1099 px layouts
  are covered. A resize through 1440 px restores the original footer nodes.

Validation: 15 JavaScript tests, 18 asset/build tests and 10 browser tests passed.
Build and build freshness checks passed.

Suggested previews:

- `mobile-header-reading-390-dark.png`: the mobile reading header.
- `mobile-topbar-cite.png`: Cite menu anchored below the header icon.
- `mobile-header-guest-answer-320.png`: all controls and login fit at 320 px.
- `mobile-topbar-sidebar-watches.png`: view switch in the opened sidebar.
- `mobile-topbar-new-chat.png`: empty composer after New chat.
