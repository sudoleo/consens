# Making this kind of film with Codex

## Start with a story that fits on one page

Name the audience, one takeaway and one action the viewer should take. Write the
question, example answers, synthesis and disagreement together. In this film,
several useful suggestions become a richer answer; the model comparison is not
a majority vote. The source check explains a conditional feature without
claiming that the illustrated reminder example produced a verified verdict.

Use [the current brief](brief.md) as an example. Keep a current source tree and
use Git commits for code history. Put disposable renders in `output/`. Do not
make each version load the previous version's HTML, audio or renderer.

## Prove the difficult middle first

Build a short moving sample of the hardest transition, here “contributions →
synthesis → visible checking.” Judge it at normal speed before polishing an
entire film. A stronger intro does not fix a static or confusing middle.

One visual focus at a time is usually enough. Extra arrows, flying dots,
miniature cards and explanations competed for attention in early versions.
The retained judge scene shows Coverage, then Differences, then the highlight.
If more explanation is necessary, give it time or remove another idea.

Keep object identity across transitions. Incoming text should not overlap the
outgoing question. A highlighted phrase should remain one glyph run as it moves:
changing font weight or replacing text mid-transition can produce a visible jump.
Move the cursor with acceleration, braking and a pause before clicking.

The original visual references were the opening of
[Magnific](https://www.youtube.com/watch?v=WM0SEHVh-j4) and the purposeful camera
movement in [Higgsfield](https://www.youtube.com/watch?v=9APVoE65qfs).
Reference downloads and copied third-party implementations are not render inputs.

## How this renderer works

1. `render.cjs` reads `content.json`, `timing.json` and local assets. It embeds
   everything into `output/source.html`; there are no remote font or image loads.
2. `initFullFilm(data)` initializes a 1080 × 1350 canvas. `drawFullFilm(seconds)`
   redraws it entirely from a requested timestamp. Rendering and QA use this
   same function, including after seeking backwards.
3. The source timeline lasts 50 seconds. Ten reading windows add seven seconds.
   The output-to-source mapping slows selected narrative moments. Judge loaders,
   checkmarks, highlighting and reader cursors use continuous output time so
   those reading windows cannot freeze an animation.
4. Playwright runs Chrome and captures each of the 3,420 frames. FFmpeg encodes
   JPEG frames to H.264 (CRF 16, yuv420p, fast-start MP4), then copies the included
   AAC soundtrack without re-encoding it.
5. QA decodes the finished file, checks dimensions/frame count/audio, and makes
   contact sheets and focused clips for review.

The two scene files communicate through `window.initStudy`, `window.drawStudy`,
`window.studyReport`, `window.initFullFilm` and `window.drawFullFilm` inside the
generated page only. They have no contract with the parent app's `window.App`.
`full-film-study.js` loads before `full-film-scene.js`.

## Iterate with evidence

Run `npm run check`, then inspect `output/qa/stills/`. For easier sheets, run
`python src/qa.py --stills`. Once those look right, render and run `npm run qa`.
Review the actual encoded MP4, especially transitions and cursor travel.

Use feedback in the form “timestamp → observation → effect → specific change.”
Fix a few consequential issues per pass. Readability, meaning and visual
continuity matter more than adding motion to every quiet moment. A pause should
give the viewer something worth reading or understanding.

Distinguish checks that passed from subjective judgments. Deterministic seeking,
error-free decoding and valid audio levels are useful evidence, but do not prove
that a scene feels good. Watch it at phone size, muted and with sound, before
publication. For a different aspect ratio, recompose the scenes instead of
stretching the existing canvas.

## A starting prompt

```text
Read the current brief and production notes. Keep one editable source tree.
First identify the hardest explanatory transition and propose a concrete
visual treatment with one focus at a time. Build a short playable sample.
Use deterministic time for drawing; keep reading time separate from active
loader and cursor motion. Review the actual encoded clip and report specific
remaining weaknesses. Once the direction is selected, apply it to the full
story and run the render and media checks. Preserve attribution.
```
