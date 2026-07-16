from __future__ import annotations

import re
import secrets
from uuid import uuid4

from flask import current_app, g, request


_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def _request_id() -> str:
    supplied = request.headers.get("X-Request-ID", "").strip()
    if supplied and _REQUEST_ID_PATTERN.fullmatch(supplied):
        return supplied
    return uuid4().hex


def prepare_request_security_context() -> None:
    g.csp_nonce = secrets.token_urlsafe(24)
    g.request_id = _request_id()


def csp_nonce() -> str:
    return getattr(g, "csp_nonce", "")


def _content_security_policy() -> str:
    nonce = csp_nonce()
    directives = [
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        f"script-src 'self' 'nonce-{nonce}'",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com data:",
        "img-src 'self' data:",
        "connect-src 'self'",
        "media-src 'self'",
        "manifest-src 'self'",
        "worker-src 'self'",
    ]
    if current_app.config.get("ENVIRONMENT_NAME") == "production":
        directives.extend(["upgrade-insecure-requests", "block-all-mixed-content"])
    return "; ".join(directives)


def apply_response_security(response):
    response.headers.setdefault("X-Request-ID", getattr(g, "request_id", ""))
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    )
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    response.headers.setdefault("Content-Security-Policy", _content_security_policy())

    if request.endpoint == "static":
        if request.args.get("v"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "public, no-cache"
    else:
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        response.headers.setdefault("Pragma", "no-cache")

    if current_app.config.get("ENVIRONMENT_NAME") == "production":
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )

    return response
