# Audio inputs

- `soundtrack.m4a`: the existing v30 AAC packets, extracted without re-encoding.
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
overwrite `soundtrack.m4a`. A new encoding can differ from the accepted AAC.

For a fresh checkout, obtain the original from the
[composer's track page](https://www.scottbuckley.com.au/library/neon/) using its
No Melody alternate mix, save it as `assets/audio/neon-source.mp3`, and check
that its SHA-256 matches `credit.json` before rebuilding. The script checks it.
Keep the [asset attribution](../../THIRD_PARTY_NOTICES.md) with any distribution.
