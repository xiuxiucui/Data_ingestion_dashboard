"""Thread-safe in-memory repository used by the services."""

from __future__ import annotations

from threading import RLock
from typing import Any

from pydantic import BaseModel

from backend.models import DashboardConfig, SchemaRegistration


class InMemoryRepository:
    """Own all process-local application state."""

    def __init__(self) -> None:
        self._schemas: dict[str, SchemaRegistration] = {}
        self._row_models: dict[str, type[BaseModel]] = {}
        self._rows: dict[str, list[dict[str, Any]]] = {}
        self._dashboards: dict[str, DashboardConfig] = {}
        self._lock = RLock()

    def add_schema(
        self,
        schema: SchemaRegistration,
        row_model: type[BaseModel],
    ) -> bool:
        with self._lock:
            if schema.name in self._schemas:
                return False
            self._schemas[schema.name] = schema
            self._row_models[schema.name] = row_model
            self._rows[schema.name] = []
            return True

    def get_schema(self, name: str) -> SchemaRegistration | None:
        with self._lock:
            return self._schemas.get(name)

    def get_row_model(self, schema_name: str) -> type[BaseModel] | None:
        with self._lock:
            return self._row_models.get(schema_name)

    def append_rows(self, schema_name: str, rows: list[dict[str, Any]]) -> int:
        with self._lock:
            self._rows[schema_name].extend(dict(row) for row in rows)
            return len(self._rows[schema_name])

    def get_rows(self, schema_name: str) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._rows.get(schema_name, [])]

    def add_dashboard(self, dashboard: DashboardConfig) -> bool:
        with self._lock:
            if dashboard.name in self._dashboards:
                return False
            self._dashboards[dashboard.name] = dashboard
            return True

    def get_dashboard(self, name: str) -> DashboardConfig | None:
        with self._lock:
            return self._dashboards.get(name)

