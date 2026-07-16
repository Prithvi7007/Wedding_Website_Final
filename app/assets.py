from __future__ import annotations

from flask import current_app, url_for


def asset_url(filename: str) -> str:
    """Return a cache-safe static URL tied to the deployed release version."""
    version = str(current_app.config.get("ASSET_VERSION", "development"))
    return url_for("static", filename=filename, v=version)
