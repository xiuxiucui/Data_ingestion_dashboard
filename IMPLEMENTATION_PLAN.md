# Backend Implementation Plan

This document turns the requirements in `requirement.md` into an implementation checklist. It should be kept up to date when the backend design changes.

## Scope

Build the required backend using Flask, Pydantic v2, and pandas-backed in-memory storage, then add a lightweight browser UI for exercising the completed API.

## Key Design Decisions

- Use Flask for HTTP routing and application setup.
- Use Pydantic for request validation and for dynamically generated row models.
- Log request metadata, complete JSON bodies, and response outcomes at `INFO` using fixed application settings.
- Store each schema's ingested rows in a typed pandas DataFrame. Keep schemas,
  generated row models, and dashboard configurations in memory.
- Treat Pydantic as the validation boundary and pandas as the storage and
  dashboard calculation engine.
- Return DataFrame copies to readers and normalize pandas missing/scalar values
  before JSON serialization.
- Require each dashboard configuration to name its source schema. The assignment example omits this relationship, but dashboard generation cannot reliably select data without it.
- Validate ingestion batches atomically: store all rows only when every row is valid.
- Reject implicit type coercion, unknown fields, duplicate names, and incompatible dashboard configurations.
- Accept JSON for the MVP. YAML dashboard input is optional and can be added later.

## Supported Schema Types

| Schema type | Python/Pydantic type |
| --- | --- |
| `string` | strict string |
| `number` | strict integer or strict float |
| `integer` | strict integer |
| `boolean` | strict boolean |

Accepted values are stored using pandas `string`, `Float64`, `Int64`, and
`boolean` dtypes respectively. These nullable dtypes allow optional fields to be
represented without changing a column's declared type.

Optional fields may be omitted or set to `null`. Required fields must be present and non-null.

## API Contract

### `POST /schema`

Register a schema, its fields, their types, required flags, and optional aggregation metadata.

Validation:

- Schema names must be unique.
- Field names must be unique within a schema.
- Field types must be supported.
- Field and schema names must use the documented name format.
- Aggregation metadata must be compatible with the field type.

Success status: `201 Created`.

### `POST /ingest`

Validate each row against the dynamic Pydantic model belonging to the named schema.

Validation:

- The schema must exist.
- Required fields must exist.
- Values must have the declared types without coercion.
- Unknown fields must be rejected.
- The complete batch must pass before any rows are stored.

Success status: `201 Created`.

### `POST /dashboard`

Register a named dashboard configuration associated with one schema.

Supported views:

- `summary`: `sum`, `average`, `min`, `max`, or `count`
- `table`: a configured list of columns

Validation:

- Dashboard names must be unique.
- The referenced schema must exist.
- Summary fields and table columns must exist.
- Numeric aggregations must target numeric fields.
- Table columns must not be repeated.

Success status: `201 Created`.

### `GET /dashboard/<name>`

Evaluate each configured view, in order, against the rows belonging to the dashboard's schema.

- Summary views return their field, aggregation, and calculated value.
- Table views return their configured columns and projected rows.
- Empty numeric collections return `0` for `sum` and `null` for `average`, `min`, and `max`.
- `count` counts rows whose selected field is not `null`.

Success status: `200 OK`.

## Error Contract

All failures use one envelope:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request could not be validated.",
    "details": []
  }
}
```

Expected status codes:

- `400 Bad Request`: malformed JSON, invalid request, invalid rows, or invalid configuration
- `404 Not Found`: unknown schema or dashboard
- `409 Conflict`: duplicate schema or dashboard
- `415 Unsupported Media Type`: a write request is not JSON
- `500 Internal Server Error`: unexpected failures

## Project Structure

```text
README.md
AI_REPORT.md
IMPLEMENTATION_PLAN.md
requirements.txt
backend/
|-- __init__.py
|-- app.py
|-- errors.py
|-- models.py
|-- storage.py
`-- services.py
frontend/
|-- templates/
`-- static/
tests/
|-- conftest.py
|-- test_schemas.py
|-- test_ingestion.py
|-- test_dashboards.py
`-- test_ui.py
```

## Implementation Checklist

- [x] Set up the Flask application factory and error handlers.
- [x] Define the Pydantic request and configuration models.
- [x] Implement schema registration and dynamic row model generation.
- [x] Implement atomic row ingestion.
- [x] Implement dashboard configuration validation and storage.
- [x] Implement summary and table view generation.
- [x] Add endpoint and service-level test coverage.
- [x] Write the README setup and usage guide.
- [x] Provide copy-ready JSON request bodies and expected responses for Bruno. Do not use `curl` commands.
- [x] Write the one-page AI workflow report.
- [x] Run the complete test suite and manually exercise the main workflow.
- [x] Add correlated request/response logging with configurable body logging.
- [x] Add a lightweight browser UI for the complete API workflow.
- [x] Replace row dictionaries with per-schema pandas DataFrames.
- [x] Use pandas for table projection, grouped aggregation, and summary calculations.
- [x] Normalize pandas missing values and scalar results for JSON responses.

## Test Checklist

- Register a valid schema.
- Reject duplicate schema names and duplicate field names.
- Reject unsupported types and invalid aggregation metadata.
- Accept valid rows.
- Reject missing required fields, incorrect types, and unknown fields.
- Confirm that an invalid batch stores no rows.
- Reject dashboards that reference missing schemas or fields.
- Reject numeric aggregations on non-numeric fields.
- Generate correct `sum`, `average`, `min`, `max`, and `count` results.
- Generate table rows containing only configured columns.
- Handle empty datasets consistently.
- Keep data from different schemas isolated.

## Deferred Work

- Advanced dashboard visualizations
- Restart-safe storage, schema migrations, and multi-process coordination
- Table pagination, filtering, sorting, and response-size limits
