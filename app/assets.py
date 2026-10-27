from __future__ import annotations

from functools import lru_cache
import hashlib
from pathlib import Path

from flask import current_app, url_for


@lru_cache(maxsize=1024)
def _content_fingerprint(path: str, mtime_ns: int, ctime_ns: int, size: int) -> str:
    """Hash static bytes once per file revision (not once per request)."""
    # Timestamps and size are part of the cache key; content remains the
    # authority for the URL, regardless of the deployment's ASSET_VERSION.
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def asset_url(filename: str) -> str:
    """Produce content-addressed URLs so immutable Nginx caching stays safe.

    A code-only release no longer needs a manual ASSET_VERSION environment
    edit. Changing an asset changes its URL even if its filename stays put.
    """
    root = Path(current_app.static_folder).resolve()
    asset = (root / filename).resolve()
    if not asset.is_relative_to(root) or not asset.is_file():
        raise ValueError("Static asset path is not an existing application file.")

    info = asset.stat()
    fingerprint = _content_fingerprint(
        str(asset), info.st_mtime_ns, info.st_ctime_ns, info.st_size
    )
    return url_for("static", filename=filename, v=fingerprint)
