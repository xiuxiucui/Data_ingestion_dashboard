"""Flask application factory and HTTP routes."""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from flask import Flask, jsonify, render_template, request
from pydantic import BaseModel, ValidationError
from werkzeug.exceptions import BadRequest, HTTPException

from backend.errors import ApiError, format_validation_errors
from backend.logging_config import configure_logging, request_id
from backend.models import DashboardConfig, IngestRequest, SchemaRegistration
from backend.services import DashboardService, IngestionService, SchemaService
from backend.storage import InMemoryRepository


RequestModel = TypeVar("RequestModel", bound=BaseModel)
FRONTEND_ROOT = Path(__file__).resolve().parent.parent / "frontend"


def create_app(repository: InMemoryRepository | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(FRONTEND_ROOT / "templates"),
        static_folder=str(FRONTEND_ROOT / "static"),
        static_url_path="/static",
    )
    app.config.from_mapping(
        JSON_SORT_KEYS=False,  # preserve original JSON order
        LOG_LEVEL="INFO",
        LOG_REQUEST_BODY=True,
        LOG_BODY_MAX_LENGTH=4096,
    )
    configure_logging(app)

    data_store = repository or InMemoryRepository()
    schema_service = SchemaService(data_store)
    ingestion_service = IngestionService(data_store)
    dashboard_service = DashboardService(data_store)
    app.extensions["repository"] = data_store

    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        app.logger.warning(
            "API error request_id=%s status=%s code=%s message=%s",
            request_id(),
            error.status_code,
            error.code,
            error.message,
        )
        return jsonify(error.to_payload()), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        api_error = ApiError(
            error.code or 500,
            error.name.upper().replace(" ", "_"),
            error.description,
        )
        app.logger.warning(
            "HTTP error request_id=%s status=%s code=%s message=%s",
            request_id(),
            api_error.status_code,
            api_error.code,
            api_error.message,
        )
        return jsonify(api_error.to_payload()), api_error.status_code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        app.logger.exception(
            "Unhandled application error request_id=%s",
            request_id(),
        )
        api_error = ApiError(
            500,
            "INTERNAL_SERVER_ERROR",
            "An unexpected error occurred.",
        )
        return jsonify(api_error.to_payload()), 500

    def parse_json(model: type[RequestModel]) -> RequestModel:
        if not request.is_json:
            raise ApiError(
                415,
                "UNSUPPORTED_MEDIA_TYPE",
                "Content-Type must be application/json.",
            )
        try:
            payload = request.get_json()
        except BadRequest as error:
            raise ApiError(400, "MALFORMED_JSON", "The request body is not valid JSON.") from error

        try:
            return model.model_validate(payload)
        except ValidationError as error:
            raise ApiError(
                400,
                "REQUEST_VALIDATION_ERROR",
                "The request body could not be validated.",
                format_validation_errors(error),
            ) from error

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/schema")
    def register_schema():
        result = schema_service.register(parse_json(SchemaRegistration))
        return jsonify(result), 201

    @app.post("/ingest")
    def ingest_rows():
        result = ingestion_service.ingest(parse_json(IngestRequest))
        return jsonify(result), 201

    @app.post("/dashboard")
    def register_dashboard():
        result = dashboard_service.register(parse_json(DashboardConfig))
        return jsonify(result), 201

    @app.get("/dashboard/<name>")
    def generate_dashboard(name: str):
        return jsonify(dashboard_service.generate(name))

    return app


if __name__ == "__main__":
    create_app().run(debug=True)

