# Audio inputs

- `soundtrack.m4a`: the 60-second AAC music edit rebuilt for the cinematic opening.
  The renderer copies this track into the new MP4.
- [credit.json](credit.json): source, license credit, original SHA-256 and edit
  parameters retained from the current film.
- `neon-source.mp3`: full original track, retained locally and ignored by Git.
  It is only needed to recreate the music edit.

The optional rebuild command is:

```sh
python src/rebuild-audio.py
```

Run it from the video directory after installing the Python dependencies. It
writes WAV files and a fresh credit into `output/audio-rebuild/`; it does not
overwrite `soundtrack.m4a`. A new encoding can differ from the included AAC. To adopt a rebuilt score,
encode `output/audio-rebuild/score.wav` to AAC at 192 kbit/s as
`assets/audio/soundtrack.m4a`, and copy the rebuilt `music-credit.json` to
`assets/audio/credit.json`. Render and run QA after updating both.

For a fresh checkout, obtain the original from the
[composer's track page](https://www.scottbuckley.com.au/library/neon/) using its
No Melody alternate mix, save it as `assets/audio/neon-source.mp3`, and check
that its SHA-256 matches `credit.json` before rebuilding. The script checks it.
Keep the [asset attribution](../../THIRD_PARTY_NOTICES.md) with any distribution.
