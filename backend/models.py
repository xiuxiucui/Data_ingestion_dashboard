"""Pydantic models describing the public API."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


SchemaName = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z][A-Za-z0-9_-]*$",
    ),
]
FieldName = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z][A-Za-z0-9_]*$",
    ),
]


class StrictApiModel(BaseModel):
    """Base model shared by API payloads."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FieldType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"


class Aggregation(str, Enum):
    SUM = "sum"
    AVERAGE = "average"
    MIN = "min"
    MAX = "max"
    COUNT = "count"


class FieldDefinition(StrictApiModel):
    name: FieldName
    type: FieldType
    required: bool = False
    aggregation: Aggregation | None = None

    @model_validator(mode="after")
    def validate_aggregation(self) -> "FieldDefinition":
        numeric_aggregations = {
            Aggregation.SUM,
            Aggregation.AVERAGE,
            Aggregation.MIN,
            Aggregation.MAX,
        }
        numeric_types = {FieldType.NUMBER, FieldType.INTEGER}
        if self.aggregation in numeric_aggregations and self.type not in numeric_types:
            raise ValueError(
                f"aggregation '{self.aggregation.value}' requires a numeric field"
            )
        return self


class SchemaRegistration(StrictApiModel):
    name: SchemaName
    fields: list[FieldDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def fields_must_be_unique(self) -> "SchemaRegistration":
        names = [field.name for field in self.fields]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"duplicate field names: {', '.join(duplicates)}")
        return self


class IngestRequest(StrictApiModel):
    schema_name: SchemaName = Field(alias="schema")
    rows: list[dict[str, Any]] = Field(min_length=1)


class SummaryView(StrictApiModel):
    type: Literal["summary"]
    field: FieldName
    aggregation: Aggregation


class TableView(StrictApiModel):
    type: Literal["table"]
    columns: list[FieldName] = Field(min_length=1)

    @model_validator(mode="after")
    def columns_must_be_unique(self) -> "TableView":
        if len(self.columns) != len(set(self.columns)):
            raise ValueError("table columns must be unique")
        return self


class AggregateDisplayColumn(StrictApiModel):
    aggregation: Aggregation


class AggregateTableView(StrictApiModel):
    type: Literal["aggregate_table"]
    aggregate_column: FieldName
    display_columns: dict[FieldName, AggregateDisplayColumn] = Field(min_length=1)


DashboardView = Annotated[
    Union[SummaryView, TableView, AggregateTableView],
    Field(discriminator="type"),
]


class DashboardConfig(StrictApiModel):
    name: SchemaName
    schema_name: SchemaName = Field(alias="schema")
    views: list[DashboardView] = Field(min_length=1)

