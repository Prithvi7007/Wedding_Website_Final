"""Content-addressed asset URLs keep year-long immutable caches correct."""
import hashlib
import re

import pytest

from app.assets import asset_url


def test_replacing_static_file_changes_url_without_changing_release_env(app, tmp_path):
    root = tmp_path / "assets"
    root.mkdir()
    css = root / "theme.css"
    css.write_text(":root { --cream: white; }", encoding="utf-8")
    app.static_folder = str(root)

    with app.test_request_context():
        first = asset_url("theme.css")
        assert first.endswith(hashlib.sha256(css.read_bytes()).hexdigest()[:16])
        assert re.search(r"/static/theme.css\?v=[a-f0-9]{16}$", first)

        css.write_text(":root { --cream: gold; }", encoding="utf-8")
        second = asset_url("theme.css")
        assert second.endswith(hashlib.sha256(css.read_bytes()).hexdigest()[:16])
        assert second != first


def test_static_version_does_not_depend_on_manual_release_version(app, tmp_path):
    css = tmp_path / "x.css"
    css.write_text("body { color: white; }", encoding="utf-8")
    app.static_folder = str(tmp_path)
    with app.test_request_context():
        app.config["ASSET_VERSION"] = "old"
        old_url = asset_url("x.css")
        app.config["ASSET_VERSION"] = "new"
        assert asset_url("x.css") == old_url


def test_asset_url_rejects_traversal_and_missing_assets(app, tmp_path):
    app.static_folder = str(tmp_path)
    with app.test_request_context():
        with pytest.raises(ValueError):
            asset_url("../secret.txt")
        with pytest.raises(ValueError):
            asset_url("missing.css")
