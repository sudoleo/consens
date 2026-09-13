# Mobile reading header

Verified on 2026-09-13 with isolated fixture answers in the real app shell.

The screenshots show the opaque 56 px navigation surface while reading,
including light/dark mode and guest controls. The menu has a 44 × 44 px target
and a consistent SVG icon. The header yields on downward scroll and returns
on upward scroll or keyboard navigation. Opening the sidebar hides the header;
closing it restores focus to the menu button.

Validation: 8 browser tests cover widths from 320 to 1440 px, guest login,
Watch scrolling, Reduced Motion, sidebar focus and the desktop layout.
The 45 existing navigation and asset/build checks passed. `npm run build`
and the build freshness check passed.
