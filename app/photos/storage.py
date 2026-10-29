"""Private file-backed photo inbox.

Photos and metadata live in a durable host-mounted directory outside the
Git checkout and Flask static folder. No wedding database migration is needed.
All raster images are decoded and re-encoded, removing EXIF and GPS metadata.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import re
import secrets
from uuid import uuid4

from flask import current_app
from werkzeug.datastructures import FileStorage

PHOTO_ID = re.compile(r"^[a-f0-9]{32}$")
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_FILES_PER_POST = 6
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_IMAGE_PIXELS = 30_000_000
MAX_STORED_PHOTOS = 2500
MAX_SIDE = 2600


class PhotoUploadError(ValueError):
    """Safe-to-display upload validation error."""


def storage_root() -> Path | None:
    raw = str(current_app.config.get("WEDDING_PHOTO_STORAGE_DIR", "")).strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        return None
    resolved = path.resolve()
    # Never put private uploads under a public static or source directory.
    app_root = Path(current_app.root_path).resolve()
    if resolved == app_root or app_root in resolved.parents:
        return None
    return resolved


def storage_ready() -> bool:
    root = storage_root()
    if root is None:
        return False
    return all((root / sub).is_dir() and not (root / sub).is_symlink()
               for sub in ("files", "metadata")) and os.access(root / "files", os.W_OK) and os.access(root / "metadata", os.W_OK)


def _root_or_raise() -> Path:
    root = storage_root()
    if root is None or not storage_ready():
        raise PhotoUploadError("Photo sharing is not available yet. Please try later.")
    return root


def _metadata_file(root: Path, photo_id: str) -> Path:
    if not PHOTO_ID.fullmatch(photo_id):
        raise FileNotFoundError("Unknown photo.")
    return root / "metadata" / f"{photo_id}.json"


def photo_path(root: Path, photo_id: str) -> Path:
    if not PHOTO_ID.fullmatch(photo_id):
        raise FileNotFoundError("Unknown photo.")
    return root / "files" / f"{photo_id}.jpg"


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        record = json.load(handle)
    if not isinstance(record, dict):
        raise ValueError("Invalid stored photo record")
    return record


def _save_json(path: Path, record: dict) -> None:
    # The temporary file stays in the same private filesystem for atomic rename.
    temp = path.with_name(f".{path.stem}-{secrets.token_hex(8)}.tmp")
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(record, output, separators=(",", ":"), ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _normalize_image(upload: FileStorage) -> bytes:
    from PIL import Image, ImageOps, UnidentifiedImageError

    stream = upload.stream
    # Bound the actual read, regardless of a forged Content-Length header.
    raw = stream.read(MAX_IMAGE_BYTES + 1)
    if len(raw) > MAX_IMAGE_BYTES:
        raise PhotoUploadError("One photo is too large. Choose photos under 12 MB.")
    if not raw:
        raise PhotoUploadError("One of the selected files was empty.")

    try:
        with Image.open(BytesIO(raw)) as source:
            if source.format not in ALLOWED_FORMATS:
                raise PhotoUploadError("Choose JPG, PNG, or WebP photos.")
            width, height = source.size
            if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                raise PhotoUploadError("This photo has unsupported dimensions.")
            source.seek(0)
            source.load()
            turned = ImageOps.exif_transpose(source)
            turned.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
            # Fresh RGB pixels: do not preserve original EXIF, GPS, ICC or text.
            rgb = Image.new("RGB", turned.size, (250, 245, 236))
            if turned.mode in ("RGBA", "LA") or "transparency" in turned.info:
                rgba = turned.convert("RGBA")
                rgb.paste(rgba, mask=rgba.getchannel("A"))
            else:
                rgb.paste(turned.convert("RGB"))
            buffer = BytesIO()
            rgb.save(buffer, format="JPEG", quality=84, optimize=True)
            return buffer.getvalue()
    except PhotoUploadError:
        raise
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise PhotoUploadError("One photo could not be read. Try a different JPG, PNG or WebP photo.") from error


def _safe_name(value: str | None) -> str:
    # Avoid hidden control characters and noisy filenames in the admin inbox.
    text = " ".join(str(value or "").split()).strip()
    if len(text) > 60:
        raise PhotoUploadError("Please keep your name under 60 characters.")
    return text


def save_photos(uploads: list[FileStorage], name: str | None, moment: str, *, gallery_consent: bool = False) -> int:
    root = _root_or_raise()
    if not 1 <= len(uploads) <= MAX_FILES_PER_POST:
        raise PhotoUploadError("Choose between 1 and 6 photos at a time.")
    guest_name = _safe_name(name)
    if moment not in {"Wedding weekend", "Haldi", "Hindu ceremony", "Church ceremony", "Reception", "Behind the scenes"}:
        raise PhotoUploadError("Choose a valid celebration moment.")

    # Validate and normalize every file BEFORE writing any of them.
    normalized = [_normalize_image(upload) for upload in uploads]

    import fcntl
    lockfile = root / "metadata" / ".lock"
    with lockfile.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        current_count = sum(1 for path in (root / "metadata").glob("*.json")
                            if path.is_file())
        if current_count + len(normalized) > MAX_STORED_PHOTOS:
            raise PhotoUploadError("Our photo inbox is full for now. Please tell the hosts.")

        written: list[tuple[Path, Path]] = []
        try:
            for data in normalized:
                photo_id = uuid4().hex
                image_file = photo_path(root, photo_id)
                metadata_file = _metadata_file(root, photo_id)
                fd = os.open(image_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as output:
                    output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
                written.append((image_file, metadata_file))
                _save_json(metadata_file, {
                    "id": photo_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "status": "pending",
                    "gallery_consent": bool(gallery_consent),
                    "guest_name": guest_name,
                    "moment": moment,
                    "bytes": len(data),
                })
        except Exception:
            for image_file, metadata_file in written:
                image_file.unlink(missing_ok=True)
                metadata_file.unlink(missing_ok=True)
            raise
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return len(normalized)


def list_photos() -> list[dict]:
    root = _root_or_raise()
    records = []
    for item in (root / "metadata").glob("*.json"):
        if not PHOTO_ID.fullmatch(item.stem):
            continue
        try:
            record = _read_json(item)
        except (ValueError, OSError, json.JSONDecodeError):
            current_app.logger.warning("Unusable photo metadata record id=%s", item.stem)
            continue
        if record.get("id") != item.stem:
            continue
        records.append(record)
    return sorted(records, key=lambda row: row.get("created_at", ""), reverse=True)


def get_photo(photo_id: str) -> tuple[dict, Path]:
    root = _root_or_raise()
    record = _read_json(_metadata_file(root, photo_id))
    if record.get("id") != photo_id or record.get("status") == "deleted":
        raise FileNotFoundError("Unknown photo.")
    path = photo_path(root, photo_id)
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError("Photo not found.")
    return record, path


def review_photo(photo_id: str, action: str, actor: str) -> None:
    if action not in {"approve", "delete", "publish", "unpublish"}:
        raise ValueError("Unsupported review action")
    import fcntl
    root = _root_or_raise()
    with (root / "metadata" / ".lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        metadata_file = _metadata_file(root, photo_id)
        record = _read_json(metadata_file)
        if record.get("id") != photo_id or record.get("status") == "deleted":
            raise FileNotFoundError("Unknown photo.")
        if action == "approve":
            if record.get("status") != "pending":
                raise ValueError("Only pending photos can be approved.")
            record["status"] = "approved"
            record.pop("published_at", None)
        elif action == "publish":
            if record.get("status") != "approved" or record.get("gallery_consent") is not True:
                raise ValueError("Photo must be approved and consented before publication.")
            record["published_at"] = datetime.now(timezone.utc).isoformat()
        elif action == "unpublish":
            if record.get("status") != "approved":
                raise ValueError("Only approved photos can be unpublished.")
            record.pop("published_at", None)
        else:
            record["status"] = "deleted"
            record.pop("published_at", None)
        record["reviewed_by"] = actor
        record["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        if action == "delete":
            # Remove private image bytes before recording the deletion tombstone.
            photo_path(root, photo_id).unlink(missing_ok=True)
        _save_json(metadata_file, record)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
