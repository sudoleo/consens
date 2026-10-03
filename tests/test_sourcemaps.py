"""Der VLQ-Decoder und die Bundle->Quelle-Aufloesung fuer Browser-Alerts."""

from __future__ import annotations

import json

import pytest

from app.core import assets, sourcemaps
from tests.sourcemap_fixtures import encode_vlq, write_map


BUNDLE = "app.0123456789ab.js"


@pytest.fixture(autouse=True)
def fresh_cache():
    sourcemaps.clear_cache()
    yield
    sourcemaps.clear_cache()


@pytest.mark.parametrize("values", [[0], [1, -1], [15, -16, 31, 32], [1_000_000, -123_456, 0, 7]])
def test_vlq_round_trip(values):
    assert sourcemaps.decode_vlq(encode_vlq(values)) == values


def test_vlq_rejects_garbage():
    with pytest.raises(ValueError):
        sourcemaps.decode_vlq("!")
    with pytest.raises(ValueError):
        sourcemaps.decode_vlq("g")  # Fortsetzungsbit ohne Folgeziffer


def test_lookup_takes_the_nearest_preceding_segment(tmp_path):
    write_map(tmp_path, BUNDLE, ["static/js/first.js", "static/js/second.js"], [
        [(0, 0, 0, 0), (100, 0, 9, 4), (250, 1, 41, 2)],
        [(3, 1, 99, 0)],
    ])
    resolve = lambda line, col: sourcemaps.resolve_bundle_location(BUNDLE, line, col, dist_dir=tmp_path)

    assert resolve(1, 1) == "static/js/first.js:1:1"
    assert resolve(1, 101) == "static/js/first.js:10:5"
    assert resolve(1, 249) == "static/js/first.js:10:5"
    assert resolve(1, 251) == "static/js/second.js:42:3"
    assert resolve(2, 4) == "static/js/second.js:100:1"
    assert resolve(2, 3) is None  # vor dem ersten Segment der Zeile
    assert resolve(3, 1) is None  # keine solche Zeile


@pytest.mark.parametrize("bundle", [
    "../app.0123456789ab.js", "app.0123456789ab.js/../../x", "app.private.js", "evil.0123456789ab.js",
])
def test_only_allowlisted_bundle_names_reach_the_filesystem(tmp_path, bundle):
    assert sourcemaps.resolve_bundle_location(bundle, 1, 1, dist_dir=tmp_path) is None


def test_missing_or_broken_maps_resolve_to_none(tmp_path):
    assert sourcemaps.resolve_bundle_location(BUNDLE, 1, 1, dist_dir=tmp_path) is None
    (tmp_path / "head.0123456789ab.js.map").write_text("{not json", encoding="utf-8")
    assert sourcemaps.resolve_bundle_location("head.0123456789ab.js", 1, 1, dist_dir=tmp_path) is None
    (tmp_path / "auth.0123456789ab.js.map").write_text(
        json.dumps({"version": 3, "sources": ["static/js/a.js"], "mappings": "!!"}), encoding="utf-8")
    assert sourcemaps.resolve_bundle_location("auth.0123456789ab.js", 1, 1, dist_dir=tmp_path) is None


def test_untrusted_source_names_never_reach_the_alert(tmp_path):
    write_map(tmp_path, BUNDLE, ["https://evil.example/x.js", "static/../secret.py"], [
        [(0, 0, 0, 0), (10, 1, 0, 0)],
    ])
    assert sourcemaps.resolve_bundle_location(BUNDLE, 1, 1, dist_dir=tmp_path) is None
    assert sourcemaps.resolve_bundle_location(BUNDLE, 1, 11, dist_dir=tmp_path) is None


@pytest.mark.skipif(not assets.MANIFEST_FILE.exists(), reason="no build output; run npm run build")
def test_every_committed_js_bundle_has_a_resolvable_map():
    manifest = json.loads(assets.MANIFEST_FILE.read_text(encoding="utf-8"))
    for script in manifest["scripts"]:
        name = script["src"].rsplit("/", 1)[-1]
        source_map = sourcemaps._load(name, sourcemaps.DIST_DIR)
        assert source_map is not None, f"{name}.map missing: run npm run build"
        assert source_map.sources and all(
            source.startswith("static/") and (assets.ROOT / source).is_file()
            for source in source_map.sources
        ), name
        # Der __name-Helfer von keepNames am Bundle-Anfang hat kein Mapping;
        # das erste Segment ist die erste eigene Codestelle.
        line = next(index for index, (columns, _) in enumerate(source_map.lines) if columns)
        column = source_map.lines[line][0][0]
        assert sourcemaps.resolve_bundle_location(name, line + 1, column + 1) is not None
