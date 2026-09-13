"""Shared paths for the standalone video tools."""
from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('VIDEO_OUT', ROOT / 'output')).resolve()

def ffmpeg():
    if os.environ.get('FFMPEG_PATH'):
        return os.environ['FFMPEG_PATH']
    return subprocess.check_output(
        [os.environ.get('NODE_BINARY', 'node'), str(ROOT / 'src/runtime.cjs'), '--ffmpeg'],
        text=True,
    ).strip()
