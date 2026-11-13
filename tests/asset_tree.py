"""A private copy of the asset tree for tests that edit a source file.

The backend suite runs its files side by side (CI: pytest -n auto). An edit
to the checkout reaches every other worker, even half written: a test that
hashes every build input (test_dist_is_not_stale) can read a sheet empty
while another test writes it back. A test that edits a source therefore
edits this copy, which app.core.assets reads in place of the checkout for
the length of the test.
"""

from __future__ import annotations

import shutil

import pytest

from app.core import assets


@pytest.fixture
def own_asset_tree(tmp_path, monkeypatch):
    """``static/`` as the asset helpers read it (sources, bundles.json, the
    manifest and the built stylesheets), under ``tmp_path``. Yields the new
    root."""

    static = tmp_path / "static"
    for name in ("css", "js"):
        shutil.copytree(assets.STATIC_DIR / name, static / name)
    shutil.copy2(assets.STATIC_DIR / "style.css", static / "style.css")
    if assets.MANIFEST_FILE.exists():
        shutil.copytree(assets.MANIFEST_FILE.parent, static / "dist",
                        ignore=shutil.ignore_patterns("*.js", "*.map"))
    monkeypatch.setattr(assets, "ROOT", tmp_path)
    monkeypatch.setattr(assets, "STATIC_DIR", static)
    monkeypatch.setattr(assets, "BUNDLES_FILE", static / "js" / "bundles.json")
    monkeypatch.setattr(assets, "MANIFEST_FILE", static / "dist" / "manifest.json")
    monkeypatch.setattr(assets, "TYPOGRAPHY_FILE", static / "css" / "typography.css")
    assets._cache.clear()
    assets._closure_cache.clear()
    yield tmp_path
    assets._cache.clear()
    assets._closure_cache.clear()
