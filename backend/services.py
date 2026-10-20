"""Business logic for schemas, ingestion, and dashboards."""

from __future__ import annotations

from typing import Any

import pandas as pd
from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
    create_model,
)

from backend.errors import ApiError, format_validation_errors
from backend.models import (
    AggregateTableView,
    Aggregation,
    DashboardConfig,
    FieldType,
    IngestRequest,
    SchemaRegistration,
    SummaryView,
    TableView,
)
from backend.storage import PandasRepository


FIELD_TYPE_MAP: dict[FieldType, Any] = {
    FieldType.STRING: StrictStr,
    FieldType.NUMBER: StrictInt | StrictFloat,
    FieldType.INTEGER: StrictInt,
    FieldType.BOOLEAN: StrictBool,
}
NUMERIC_FIELD_TYPES = {FieldType.NUMBER, FieldType.INTEGER}
NUMERIC_AGGREGATIONS = {
    Aggregation.SUM,
    Aggregation.AVERAGE,
    Aggregation.MIN,
    Aggregation.MAX,
}


class SchemaService:
    def __init__(self, repository: PandasRepository) -> None:
        self.repository = repository

    def register(self, schema: SchemaRegistration) -> dict[str, Any]:
        row_model = self._build_row_model(schema)
        if not self.repository.add_schema(schema, row_model):
            raise ApiError(
                409,
                "SCHEMA_ALREADY_EXISTS",
                f"Schema '{schema.name}' already exists.",
            )
        return {"name": schema.name, "fields": len(schema.fields)}

    @staticmethod
    def _build_row_model(schema: SchemaRegistration) -> type[BaseModel]:
        definitions: dict[str, tuple[Any, Any]] = {}
        for field in schema.fields:
            python_type = FIELD_TYPE_MAP[field.type]
            if field.required:
                definitions[field.name] = (python_type, ...)
            else:
                definitions[field.name] = (python_type | None, None)

        class_name = "".join(part.title() for part in schema.name.replace("-", "_").split("_"))
        return create_model(
            f"{class_name}Row",
            __config__=ConfigDict(extra="forbid", strict=True),
            **definitions,
        )


class IngestionService:
    def __init__(self, repository: PandasRepository) -> None:
        self.repository = repository

    def ingest(self, request: IngestRequest) -> dict[str, Any]:
        row_model = self.repository.get_row_model(request.schema_name)
        if row_model is None:
            raise ApiError(
                404,
                "SCHEMA_NOT_FOUND",
                f"Schema '{request.schema_name}' was not found.",
            )

        validated_rows: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for index, row in enumerate(request.rows):
            try:
                validated = row_model.model_validate(row)
                validated_rows.append(validated.model_dump(mode="json"))
            except ValidationError as error:
                errors.extend(format_validation_errors(error, ("rows", index)))

        if errors:
            raise ApiError(
                400,
                "ROW_VALIDATION_ERROR",
                "One or more rows failed schema validation. No rows were stored.",
                errors,
            )

        total_rows = self.repository.append_rows(request.schema_name, validated_rows)
        return {
            "schema": request.schema_name,
            "accepted": len(validated_rows),
            "totalRows": total_rows,
        }


class DashboardService:
    def __init__(self, repository: PandasRepository) -> None:
        self.repository = repository

    def register(self, dashboard: DashboardConfig) -> dict[str, Any]:
        schema = self.repository.get_schema(dashboard.schema_name)
        if schema is None:
            raise ApiError(
                404,
                "SCHEMA_NOT_FOUND",
                f"Schema '{dashboard.schema_name}' was not found.",
            )

        fields = {field.name: field for field in schema.fields}
        details: list[dict[str, Any]] = []
        for index, view in enumerate(dashboard.views):
            if isinstance(view, SummaryView):
                field = fields.get(view.field)
                if field is None:
                    details.append(
                        {
                            "location": ["views", index, "field"],
                            "message": f"Field '{view.field}' does not exist in schema '{schema.name}'.",
                            "type": "unknown_field",
                        }
                    )
                elif (
                    view.aggregation in NUMERIC_AGGREGATIONS
                    and field.type not in NUMERIC_FIELD_TYPES
                ):
                    details.append(
                        {
                            "location": ["views", index, "aggregation"],
                            "message": (
                                f"Aggregation '{view.aggregation.value}' requires a numeric field."
                            ),
                            "type": "incompatible_aggregation",
                        }
                    )
            elif isinstance(view, TableView):
                for column_index, column in enumerate(view.columns):
                    if column not in fields:
                        details.append(
                            {
                                "location": ["views", index, "columns", column_index],
                                "message": (
                                    f"Field '{column}' does not exist in schema '{schema.name}'."
                                ),
                                "type": "unknown_field",
                            }
                        )
            elif isinstance(view, AggregateTableView):
                if view.aggregate_column not in fields:
                    details.append(
                        {
                            "location": ["views", index, "aggregate_column"],
                            "message": (
                                f"Field '{view.aggregate_column}' does not exist "
                                f"in schema '{schema.name}'."
                            ),
                            "type": "unknown_field",
                        }
                    )

                for column, configuration in view.display_columns.items():
                    field = fields.get(column)
                    if field is None:
                        details.append(
                            {
                                "location": [
                                    "views",
                                    index,
                                    "display_columns",
                                    column,
                                ],
                                "message": (
                                    f"Field '{column}' does not exist in schema "
                                    f"'{schema.name}'."
                                ),
                                "type": "unknown_field",
                            }
                        )
                    elif (
                        configuration.aggregation in NUMERIC_AGGREGATIONS
                        and field.type not in NUMERIC_FIELD_TYPES
                    ):
                        details.append(
                            {
                                "location": [
                                    "views",
                                    index,
                                    "display_columns",
                                    column,
                                    "aggregation",
                                ],
                                "message": (
                                    f"Aggregation "
                                    f"'{configuration.aggregation.value}' requires "
                                    "a numeric field."
                                ),
                                "type": "incompatible_aggregation",
                            }
                        )

        if details:
            raise ApiError(
                400,
                "INVALID_DASHBOARD_CONFIG",
                "The dashboard configuration is incompatible with its schema.",
                details,
            )

        if not self.repository.add_dashboard(dashboard):
            raise ApiError(
                409,
                "DASHBOARD_ALREADY_EXISTS",
                f"Dashboard '{dashboard.name}' already exists.",
            )

        return {
            "name": dashboard.name,
            "schema": dashboard.schema_name,
            "views": len(dashboard.views),
        }

    def generate(self, name: str) -> dict[str, Any]:
        dashboard = self.repository.get_dashboard(name)
        if dashboard is None:
            raise ApiError(
                404,
                "DASHBOARD_NOT_FOUND",
                f"Dashboard '{name}' was not found.",
            )

        frame = self.repository.get_dataframe(dashboard.schema_name)
        rendered_views = [self._render_view(view, frame) for view in dashboard.views]
        return {
            "name": dashboard.name,
            "schema": dashboard.schema_name,
            "views": rendered_views,
        }

    @staticmethod
    def _render_view(
        view: SummaryView | TableView | AggregateTableView,
        frame: pd.DataFrame,
    ) -> dict[str, Any]:
        if isinstance(view, TableView):
            return {
                "type": "table",
                "columns": view.columns,
                "rows": DashboardService._records(frame.loc[:, view.columns]),
            }

        if isinstance(view, AggregateTableView):
            rendered_rows = []
            groups = frame.groupby(
                view.aggregate_column,
                sort=False,
                dropna=False,
            )
            for group_value, group_frame in groups:
                rendered_values = {}
                for column, configuration in view.display_columns.items():
                    rendered_values[column] = DashboardService._aggregate(
                        group_frame[column],
                        configuration.aggregation,
                    )

                rendered_rows.append(
                    {
                        "group_value": DashboardService._json_scalar(group_value),
                        "values": rendered_values,
                    }
                )

            return {
                "type": "aggregate_table",
                "aggregate_column": view.aggregate_column,
                "display_columns": {
                    column: {"aggregation": configuration.aggregation.value}
                    for column, configuration in view.display_columns.items()
                },
                "rows": rendered_rows,
            }

        value = DashboardService._aggregate(frame[view.field], view.aggregation)

        return {
            "type": "summary",
            "field": view.field,
            "aggregation": view.aggregation.value,
            "value": value,
        }

    @staticmethod
    def _aggregate(values: pd.Series, aggregation: Aggregation) -> Any:
        values = values.dropna()
        if aggregation == Aggregation.COUNT:
            result = len(values)
        elif aggregation == Aggregation.SUM:
            result = values.sum()
        elif aggregation == Aggregation.AVERAGE:
            result = values.mean() if not values.empty else None
        elif aggregation == Aggregation.MIN:
            result = values.min() if not values.empty else None
        else:
            result = values.max() if not values.empty else None
        return DashboardService._json_scalar(result)

    @staticmethod
    def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
        return [
            {
                column: DashboardService._json_scalar(value)
                for column, value in zip(frame.columns, row, strict=True)
            }
            for row in frame.itertuples(index=False, name=None)
        ]

    @staticmethod
    def _json_scalar(value: Any) -> Any:
        if value is None or pd.isna(value):
            return None
        if hasattr(value, "item"):
            return value.item()
        return value

