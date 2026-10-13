"""Application logging configuration and HTTP request logging hooks."""

from __future__ import annotations

import json
import logging
from time import perf_counter
from typing import Any
from uuid import uuid4

from flask import Flask, g, request


def configure_logging(app: Flask) -> None:
    """Configure application logging and register request lifecycle hooks."""

    level_name = str(app.config["LOG_LEVEL"]).upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )

    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(level)
    app.logger.propagate = False

    @app.before_request
    def log_incoming_request() -> None:
        g.request_started_at = perf_counter()
        supplied_request_id = request.headers.get("X-Request-ID", "").strip()
        g.request_id = supplied_request_id[:128] or uuid4().hex

        app.logger.info(
            "Incoming request request_id=%s method=%s path=%s "
            "remote_addr=%s content_length=%s",
            g.request_id,
            request.method,
            request.path,
            request.remote_addr or "unknown",
            request.content_length if request.content_length is not None else 0,
        )

        if app.config["LOG_REQUEST_BODY"] and request.is_json:
            payload = request.get_json(silent=True)
            if payload is not None:
                app.logger.info(
                    "Request body request_id=%s body=%s",
                    g.request_id,
                    _serialize_payload(
                        payload,
                        max_length=app.config["LOG_BODY_MAX_LENGTH"],
                    ),
                )

    @app.after_request
    def log_completed_request(response):
        request_id = getattr(g, "request_id", uuid4().hex)
        started_at = getattr(g, "request_started_at", perf_counter())
        duration_ms = (perf_counter() - started_at) * 1000
        response.headers["X-Request-ID"] = request_id

        log_method = app.logger.warning if response.status_code >= 400 else app.logger.info
        log_method(
            "Completed request request_id=%s method=%s path=%s "
            "status=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
        return response


def request_id() -> str:
    """Return the current request ID for error log correlation."""

    return getattr(g, "request_id", "unknown")


def _serialize_payload(payload: Any, max_length: int) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    if len(serialized) <= max_length:
        return serialized
    return f"{serialized[:max_length]}...<truncated>"

