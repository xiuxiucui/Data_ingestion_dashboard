"""Thread-safe, pandas-backed in-memory repository used by the services."""

from __future__ import annotations

from threading import RLock
from typing import Any

import pandas as pd
from pydantic import BaseModel

from backend.models import DashboardConfig, FieldType, SchemaRegistration


PANDAS_DTYPES: dict[FieldType, str] = {
    FieldType.STRING: "string",
    FieldType.NUMBER: "Float64",
    FieldType.INTEGER: "Int64",
    FieldType.BOOLEAN: "boolean",
}


class PandasRepository:
    """Own all process-local state and keep each schema's rows in a DataFrame."""

    def __init__(self) -> None:
        self._schemas: dict[str, SchemaRegistration] = {}
        self._row_models: dict[str, type[BaseModel]] = {}
        self._frames: dict[str, pd.DataFrame] = {}
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
            self._frames[schema.name] = self._empty_frame(schema)
            return True

    @staticmethod
    def _empty_frame(schema: SchemaRegistration) -> pd.DataFrame:
        return pd.DataFrame(
            {
                field.name: pd.Series(dtype=PANDAS_DTYPES[field.type])
                for field in schema.fields
            }
        )

    def get_schema(self, name: str) -> SchemaRegistration | None:
        with self._lock:
            return self._schemas.get(name)

    def get_row_model(self, schema_name: str) -> type[BaseModel] | None:
        with self._lock:
            return self._row_models.get(schema_name)

    def append_rows(self, schema_name: str, rows: list[dict[str, Any]]) -> int:
        with self._lock:
            current = self._frames[schema_name]
            incoming = pd.DataFrame.from_records(rows, columns=current.columns)
            incoming = incoming.astype(current.dtypes.to_dict())
            self._frames[schema_name] = (
                incoming.reset_index(drop=True)
                if current.empty
                else pd.concat([current, incoming], ignore_index=True)
            )
            return len(self._frames[schema_name])

    def get_dataframe(self, schema_name: str) -> pd.DataFrame:
        """Return an isolated snapshot so callers cannot mutate stored data."""
        with self._lock:
            frame = self._frames.get(schema_name)
            if frame is None:
                return pd.DataFrame()
            return frame.copy(deep=True)

    def get_rows(self, schema_name: str) -> list[dict[str, Any]]:
        """Return records for compatibility with repository consumers."""
        frame = self.get_dataframe(schema_name)
        return [
            {
                column: None if pd.isna(value) else value
                for column, value in zip(frame.columns, row, strict=True)
            }
            for row in frame.itertuples(index=False, name=None)
        ]

    def add_dashboard(self, dashboard: DashboardConfig) -> bool:
        with self._lock:
            if dashboard.name in self._dashboards:
                return False
            self._dashboards[dashboard.name] = dashboard
            return True

    def get_dashboard(self, name: str) -> DashboardConfig | None:
        with self._lock:
            return self._dashboards.get(name)


# Preserve the public name used by earlier versions and external tests.
InMemoryRepository = PandasRepository

