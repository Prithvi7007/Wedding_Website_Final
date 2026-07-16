from __future__ import annotations

import logging
from logging.config import dictConfig

from flask import g, has_request_context


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(g, "request_id", "-") if has_request_context() else "-"
        return True


def configure_logging(level: str) -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_context": {"()": RequestContextFilter},
            },
            "formatters": {
                "default": {
                    "format": (
                        "%(asctime)s %(levelname)s %(name)s "
                        "request_id=%(request_id)s %(message)s"
                    )
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "filters": ["request_context"],
                }
            },
            "root": {
                "level": level,
                "handlers": ["console"],
            },
        }
    )
