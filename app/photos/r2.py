"""Private Cloudflare R2 storage for wedding photos and recovery metadata.

No bucket credentials or object URLs ever leave the server. All image bytes are
normalized by the wedding upload validator before reaching this adapter.
"""
from __future__ import annotations

from io import BytesIO
import json
import re

from flask import current_app


_ID = re.compile(r"^[a-f0-9]{32}$")
_ACCOUNT = re.compile(r"^[a-f0-9]{32}$")
_BUCKET = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")
MAX_OBJECT_BYTES = 20 * 1024 * 1024


class RemotePhotoError(RuntimeError):
    """Cloud-storage failure with a safe message for the user."""


def configured() -> bool:
    cfg = current_app.config
    return (
        bool(_ACCOUNT.fullmatch(str(cfg.get("WEDDING_R2_ACCOUNT_ID", ""))))
        and bool(_BUCKET.fullmatch(str(cfg.get("WEDDING_R2_BUCKET", ""))))
        and len(str(cfg.get("WEDDING_R2_ACCESS_KEY_ID", ""))) >= 12
        and len(str(cfg.get("WEDDING_R2_SECRET_ACCESS_KEY", ""))) >= 16
    )


def _key(photo_id: str, kind: str) -> str:
    if not _ID.fullmatch(photo_id):
        raise FileNotFoundError("Unknown photo.")
    if kind not in ("photos", "metadata"):
        raise ValueError("Unknown photo object category.")
    return f"wedding/{kind}/{photo_id}.{'jpg' if kind == 'photos' else 'json'}"


def _client():
    if not configured():
        raise RemotePhotoError("Cloud photo storage is not configured.")
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise RemotePhotoError("Cloud photo storage dependencies are unavailable.") from exc
    cfg = current_app.config
    return boto3.client(
        "s3",
        endpoint_url=f"https://{cfg['WEDDING_R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        region_name="auto",
        aws_access_key_id=cfg["WEDDING_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=cfg["WEDDING_R2_SECRET_ACCESS_KEY"],
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=15,
            retries={"max_attempts": 2},
        ),
    )


def _bucket() -> str:
    return str(current_app.config["WEDDING_R2_BUCKET"])


def put_image(photo_id: str, contents: bytes) -> None:
    if len(contents) > MAX_OBJECT_BYTES:
        raise RemotePhotoError("Photo is too large to store.")
    try:
        _client().put_object(
            Bucket=_bucket(), Key=_key(photo_id, "photos"),
            Body=contents, ContentType="image/jpeg",
            CacheControl="private, no-store",
        )
    except RemotePhotoError:
        raise
    except Exception as exc:
        current_app.logger.error("Cloud photo upload failed id=%s", photo_id)
        raise RemotePhotoError("Cloud photo storage is temporarily unavailable.") from exc


def get_image(photo_id: str) -> BytesIO:
    try:
        obj = _client().get_object(Bucket=_bucket(), Key=_key(photo_id, "photos"))
        body = obj["Body"]
        try:
            contents = body.read(MAX_OBJECT_BYTES + 1)
        finally:
            body.close()
        if len(contents) > MAX_OBJECT_BYTES:
            raise RemotePhotoError("Stored photo exceeds allowed size.")
        return BytesIO(contents)
    except RemotePhotoError:
        raise
    except Exception as exc:
        code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
        if code in ("NoSuchKey", "NotFound", "404"):
            raise FileNotFoundError("Photo not found.") from exc
        current_app.logger.error("Cloud photo retrieval failed id=%s", photo_id)
        raise RemotePhotoError("Cloud photo storage is temporarily unavailable.") from exc


def delete_image(photo_id: str) -> None:
    try:
        _client().delete_object(Bucket=_bucket(), Key=_key(photo_id, "photos"))
    except RemotePhotoError:
        raise
    except Exception as exc:
        current_app.logger.error("Cloud photo deletion failed id=%s", photo_id)
        raise RemotePhotoError("Cloud photo storage is temporarily unavailable.") from exc


def backup_metadata(photo_id: str, record: dict) -> None:
    """Mirror private moderation state to R2; not a substitute for backups."""
    contents = json.dumps(record, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    try:
        _client().put_object(
            Bucket=_bucket(), Key=_key(photo_id, "metadata"),
            Body=contents, ContentType="application/json",
            CacheControl="private, no-store",
        )
    except RemotePhotoError:
        raise
    except Exception as exc:
        current_app.logger.error("Cloud metadata mirror failed id=%s", photo_id)
        raise RemotePhotoError("Cloud photo storage is temporarily unavailable.") from exc


def delete_metadata(photo_id: str) -> None:
    """Best-effort removal for an incomplete upload transaction."""
    try:
        _client().delete_object(Bucket=_bucket(), Key=_key(photo_id, "metadata"))
    except Exception:
        current_app.logger.warning("Cloud metadata rollback incomplete id=%s", photo_id)
