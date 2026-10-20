# Schema-Driven Dashboard Platform

A lightweight Flask API that registers data schemas, validates and ingests rows, registers dashboard configurations, and generates dashboard-ready data. Rows are held in typed, per-schema pandas DataFrames. All state is in memory and is reset whenever the application restarts.

## Features

- Dynamic Pydantic row models built from registered schemas
- Strict validation with no automatic string-to-number coercion
- Required-field and unknown-field validation
- Atomic batch ingestion
- Nullable pandas dtypes mapped from registered schema types
- Summary views using `sum`, `average`, `min`, `max`, and `count`
- Pandas-backed projection, grouping, and aggregation
- Table views containing configured columns
- Consistent JSON error responses
- Thread-safe pandas-backed in-memory storage
- Lightweight browser UI with editable example requests and rendered dashboard results

## Requirements

- Python 3.11 or newer
- Dependencies listed in `requirements.txt`

## Setup and Run

From the repository root in PowerShell:

```powershell
& .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m backend.app
```

The API and browser UI will be available at `http://127.0.0.1:5000`.

## Browser UI

Open this address after starting Flask:

```text
http://127.0.0.1:5000
```

The page contains the complete workflow in order:

1. Register the example trade schema.
2. Ingest the example trade rows.
3. Register the example dashboard.
4. Load and render the generated dashboard.

Each JSON body is editable. The UI displays the HTTP status and raw JSON response for every request, and the final step renders summary and table views. Run the steps in order because application state is stored only in memory.

## Logging and Debugging

The backend logs every incoming request and completed response. The default `INFO` level includes the request ID, HTTP method, path, remote address, content length, complete JSON request body, response status, and processing time.

Request-body logging is enabled by default. Start the backend normally:

```powershell
python -m backend.app
```

Example output:

```text
INFO backend.app Incoming request request_id=... method=POST path=/schema remote_addr=127.0.0.1 content_length=245
INFO backend.app Request body request_id=... body={"name":"trade","fields":[...]}
INFO backend.app Completed request request_id=... method=POST path=/schema status=201 duration_ms=1.24
```

The complete payload is logged as received. Bodies longer than 4096 characters are truncated. These fixed settings are defined in the Flask application factory.

The backend accepts an optional `X-Request-ID` request header and returns the same value in the response. If it is not provided, the backend generates one. Use this ID to match an error response with its server logs.

Check that it is running with a `GET` request in Bruno:

```text
http://127.0.0.1:5000/health
```

Expected response:

```json
{
  "status": "ok"
}
```

## Bruno Workflow

For each `POST` request, select **Body**, choose **raw**, and select **JSON** as the content type. Run these requests in order because the data is stored in memory.

### 1. Register a schema

Method and URL:

```text
POST http://127.0.0.1:5000/schema
```

Copy this JSON into Bruno:

```json
{
  "name": "trade",
  "fields": [
    {
      "name": "tradeId",
      "type": "string",
      "required": true
    },
    {
      "name": "amount",
      "type": "number",
      "required": true,
      "aggregation": "sum"
    },
    {
      "name": "status",
      "type": "string"
    }
  ]
}
```

Expected `201 Created` response:

```json
{
  "fields": 3,
  "name": "trade"
}
```

Supported field types are `string`, `number`, `integer`, and `boolean`.

### 2. Ingest data

Method and URL:

```text
POST http://127.0.0.1:5000/ingest
```

Copy this JSON into Bruno:

```json
{
  "schema": "trade",
  "rows": [
    {
      "tradeId": "T001",
      "amount": 1000,
      "status": "OPEN"
    },
    {
      "tradeId": "T002",
      "amount": 1500.5,
      "status": "CLOSED"
    }
  ]
}
```

Expected `201 Created` response:

```json
{
  "accepted": 2,
  "schema": "trade",
  "totalRows": 2
}
```

The batch is atomic. If any row is invalid, no rows from that request are stored.

### 3. Register a dashboard

Method and URL:

```text
POST http://127.0.0.1:5000/dashboard
```

Copy this JSON into Bruno:

```json
{
  "name": "trade-dashboard",
  "schema": "trade",
  "views": [
    {
      "type": "summary",
      "field": "amount",
      "aggregation": "sum"
    },
    {
      "type": "table",
      "columns": [
        "tradeId",
        "amount",
        "status"
      ]
    }
  ]
}
```

Expected `201 Created` response:

```json
{
  "name": "trade-dashboard",
  "schema": "trade",
  "views": 2
}
```

The `schema` property is required so the backend knows which ingested dataset the dashboard should use.

### 4. Generate dashboard data

Method and URL:

```text
GET http://127.0.0.1:5000/dashboard/trade-dashboard
```

Expected `200 OK` response:

```json
{
  "name": "trade-dashboard",
  "schema": "trade",
  "views": [
    {
      "aggregation": "sum",
      "field": "amount",
      "type": "summary",
      "value": 2500.5
    },
    {
      "columns": [
        "tradeId",
        "amount",
        "status"
      ],
      "rows": [
        {
          "amount": 1000,
          "status": "OPEN",
          "tradeId": "T001"
        },
        {
          "amount": 1500.5,
          "status": "CLOSED",
          "tradeId": "T002"
        }
      ],
      "type": "table"
    }
  ]
}
```

## Validation Error Example

Submitting `"amount": "1000"` is rejected because numeric strings are not coerced. Errors use this shape:

```json
{
  "error": {
    "code": "ROW_VALIDATION_ERROR",
    "message": "One or more rows failed schema validation. No rows were stored.",
    "details": [
      {
        "location": [
          "rows",
          0,
          "amount",
          "int"
        ],
        "message": "Input should be a valid integer",
        "type": "int_type"
      }
    ]
  }
}
```

For a `number` field, Pydantic may return one validation detail for its integer option and another for its floating-point option.

## Run Tests

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

The test suite covers schema registration, strict row validation, atomic batches, dashboard configuration validation, dashboard generation, and UI asset delivery.

## Project Layout

```text
backend/
|-- app.py       # Flask application factory and routes
|-- errors.py    # Stable API error representation
|-- models.py    # Pydantic request/configuration models
|-- services.py  # Business logic and dynamic row models
`-- storage.py   # Thread-safe pandas DataFrame repository
frontend/
|-- templates/   # Browser workbench HTML
`-- static/      # UI styles and request-handling JavaScript
tests/           # Endpoint tests using the Flask test client
```

See `IMPLEMENTATION_PLAN.md` for the design decisions and implementation checklist.

