# Source-check presentation

The result card now has an inset navigation cue, internal spacing, a small
status label, and concise guidance when a check cannot settle a disagreement.
It keeps the original verdict, explanation and evidence; rejected evidence
never receives a positive status, even with contradictory saved flags.

Review images use fixture answers in the real app shell, with no live model
requests or production data:

- `contradiction-evidence-unavailable-1440.png`: desktop result and full border.
- `contradiction-evidence-unavailable-320.png`: narrow mobile result.
- `contradiction-evidence-unavailable-dark-390.png`: dark mobile result.
- `source-check-jump-1440.png`: completed check, evidence initially collapsed.
- `excluded-source-390.png`: excluded check with explanation and guidance.

Validation: 107 targeted JavaScript tests, 18 asset/build tests, and 7 browser
tests. Browser coverage includes 320/390/1440 px, light/dark themes, focus,
highlight expiration, clipped ancestors, reduced motion, and forced colors.

The build-size regression also now compares normalized LF bytes across
platforms. The previous committed baseline was 50.8% of its LF input size,
already above the old 50% threshold; CRLF expansion masked that on Windows.
The check now requires at least 45% savings, with separate checks for request
count, content freshness, and public JavaScript contracts.
