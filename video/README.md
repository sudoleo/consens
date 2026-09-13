# consens.io product video

A 57-second product film built with Canvas, Playwright and FFmpeg, developed
with Codex. This is the consolidated v30 composition: one source tree, one
timeline and one render destination. It renders without the consens.io app,
Firebase, API keys or previous video versions.

The workflow is illustrated with authored example answers. It is not a recording
of a live model run. The current composition is 1080 × 1350, 60 fps, with music
and no voiceover.

## Run it

Install Node.js 18+ (a recent LTS is preferable), Chrome/Chromium and Python 3.9+.
Run these commands **inside this directory**, including after copying it into
a separate repository:

```sh
npm ci
python -m venv .venv
```

Activate the Python environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```sh
# macOS / Linux
source .venv/bin/activate
```

Then:

```sh
python -m pip install -r requirements.txt
npm run doctor
npm run check
npm run render
npm run qa
npm run preview
```

Open [the local preview](http://127.0.0.1:8782/). `output/consensio-4x5.mp4` is
the master. QA also creates an opening clip, a source/reader clip, contact sheets
and `output/qa-summary.json`. Rendering writes to `output/`; source assets are
never regenerated implicitly. The original v30 is retained locally as
`output/accepted-v30.mp4` (SHA-256
`06bdea3c2f2d691c11de51e3a73babbaef3893fae1ce059318c66be8a902e4d6`).

`npm run check` executes the scene in headless Chrome, saves stills and checks
deterministic seeks, text continuity, judge motion, reading windows, icon
proportions and cursor pacing. `npm run qa` checks the completed MP4, including
all 3,420 decoded frames and the encoded audio against the included soundtrack.
These checks are specific to this film; adapt them deliberately when changing
its content. They do not replace watching and listening to the finished film.

In the parent app repository, `.\dev.ps1 check video` runs the same scene check.
The standalone npm commands remain the canonical entry points.

## Where to work

| Path | Purpose |
| --- | --- |
| [src/content.json](src/content.json) | Prompt, six model contributions, synthesis, reader excerpts and provider order. |
| [src/timing.json](src/timing.json) | Reading windows and continuous judge/cursor motion. |
| [src/full-film-scene.js](src/full-film-scene.js) | Opening, input, source check, reader and outro. |
| [src/full-film-study.js](src/full-film-study.js) | Model cards, synthesis, judges and the highlighted disagreement. |
| [src/render.cjs](src/render.cjs) | Asset embedding, scene checks and frame-by-frame encoding. |
| [src/qa.py](src/qa.py) | Decode, audio checks, review sheets and short clips. |
| [src/preview.html](src/preview.html), [src/preview.py](src/preview.py) | Chapter player and loopback server with byte-range seeking. |
| [assets/](assets/) | Local font, brand images, encoded soundtrack and music credits. |
| [docs/production.md](docs/production.md) | Creative workflow, timing model and lessons from iteration. |
| [docs/brief.md](docs/brief.md) | Current product, audience and design brief. |
| [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) | Music, font and brand attribution. |

Some scene labels, geometry and transitions intentionally remain in the drawing
code. This is a working example, not a general-purpose editor. Replacing text
alone will not make an unrelated product's story fit the same scene timings.

## Overrides and comparisons

`CHROME_PATH` selects a browser executable; `FFMPEG_PATH` selects a different
FFmpeg. Otherwise npm supplies the platform-specific FFmpeg and the tool looks
for Chrome in common Windows/macOS/Linux locations. `VIDEO_OUT` chooses another
output directory; relative paths resolve from the command's working directory.
Python tools honor `NODE_BINARY` if Node is not available as `node` on PATH.
Windows is the validated platform for this cleanup; other platforms can differ
in font rasterization and encoding.

Optional comparison to a previously rendered self-contained scene:

```sh
node src/render.cjs --stills --reference=/absolute/path/to/source.html
```

This checks matching output times at quarter-second intervals and all review
stills. It is for changes expected to preserve those frames; run it with the same
browser version. Ordinary rendering has no dependency on that reference.

To rebuild the music edit, see [the audio notes](assets/audio/README.md).

## Moving into its own repository

Copy this directory without `node_modules/`, `.venv/`, `.local/` or `output/`.
The checked-in npm lockfile, Python requirements and assets are sufficient for
the standard render. Keep `.gitignore` and the attribution files. Large source
music remains local and is only needed for an optional audio rebuild.

No public repository, post or source-code license has been created by this
cleanup. Choose the code license when preparing the public release; third-party
asset notices remain separate from that decision.
