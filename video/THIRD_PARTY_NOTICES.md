# Asset attribution

## Music

“Neon (No Melody Alt Mix)” by Scott Buckley. The retained production credit
identifies the track as CC BY 4.0:
[track page](https://www.scottbuckley.com.au/library/neon/),
[license](https://creativecommons.org/licenses/by/4.0/).

The film uses the passage 115.15–133.15 seconds, repeated every 16 seconds with
two-second crossfades, level adjustment, three-second fade-in and 1.45-second
fade-out. No typing sounds or typing-related ducking. Detailed source hash and
mix metadata: [assets/audio/credit.json](assets/audio/credit.json).

Credit for the video description:

> Music: “Neon (No Melody Alt Mix)” by Scott Buckley, CC BY 4.0. Edited and looped
> excerpt with crossfades, level adjustment and fades.

Include the track and license links above when publishing the film. The original
full-length MP3 is a local production input, excluded from Git; the standard
render uses the included edited soundtrack.

## Font

Inter by the Inter Project authors. The copied font retains its
[SIL Open Font License](assets/fonts/OFL.txt).

## Brand images

The consens.io logo and the model-provider icons were copied from the existing
product assets so the film can render without the app repository. They identify
the depicted product and providers. No new license or endorsement is granted
for those marks by this package. Replace them when adapting the example to
another product; a future license for the source code does not relicense them.

## Tooling

Playwright and the platform-specific FFmpeg package are npm dependencies recorded
in `package-lock.json`, not vendored source. Their notices ship with the packages.
Python dependencies are recorded in `requirements.txt`.
