I would like you to implement a Flask backend app, for data ingestion with 4 API end points. the example input is listed at the end of this file

Please use Pydantic for incoming request validation and data validation before storage.

Please take not on the following possible failure, and you need to raise exception based on it .

POST /schema
1. duplicated schema can not be create
2. there should be no field with the same name, even though their datatype is different 
3. the only supported data type should be the primary data type, reject any other data type
4. aggregation can only happen on number (int or float), not any other data type 

POST /ingest
1. do not ingest data, unless schema is already declared
2. if a field is declared required in the schema, it must be declared in ingestion data
3. type must match what is declared in the schema
4. undeclared field should not be ingested

POST /dashboard
1. dashboard creation must be tagged to a created schema(we can not create dashboard for a undeclared schema)
2. we can not create duplicated dashboard
3. reject incompatible aggregation and field


POST /schema
1. return 404 for uncreated dashboard


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

POST /ingest

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

POST /dashboard

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

GET /dashboard/{name}

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

## Version 2: Aggregate table dashboard view

Keep the existing four endpoints and the `summary` and `table` view types. Extend `POST /dashboard` so that a dashboard's `views` array can also contain an `aggregate_table` view. This view groups ingested rows by one schema field and calculates an aggregation for each configured display field within each group.

### Dashboard configuration

```json
{
  "name": "trade-dashboard-by-desk",
  "schema": "trade",
  "views": [
    {
      "type": "aggregate_table",
      "aggregate_column": "desk",
      "display_columns": {
        "amount": { "aggregation": "sum" },
        "desk": { "aggregation": "count" }
      }
    }
  ]
}
```

The example requires `desk` to be declared in the `trade` schema and present in the ingested rows. For example, rows with desks `SG`, `SG`, and `HK` produce one result row for `SG` and one for `HK`.

### Validation and calculation rules

1. `aggregate_column` is required and must name a field declared in the dashboard's schema. The grouping field may be a string, number, integer, or boolean.
2. `display_columns` is required and must contain at least one entry. Each key must name a field declared in the same schema, and each entry must specify one supported aggregation: `sum`, `average`, `min`, `max`, or `count`.
3. `sum`, `average`, `min`, and `max` require a numeric display field (`number` or `integer`). `count` is allowed for any supported field type. This clarifies the Version 1 numeric-only rule for the new view: `count` counts values rather than performing numeric arithmetic.
4. For each distinct `aggregate_column` value, calculate each display field's aggregation using only rows in that group. Ignore null values in the display field when calculating aggregates. `count` returns the number of non-null values; `sum` returns `0` when there are none; `average`, `min`, and `max` return `null` when there are none.
5. A null grouping value forms its own group. Return groups in the order their values first appear in the ingested rows. If no rows have been ingested, return an empty `rows` array.
6. Reject unknown fields, missing configuration, unsupported aggregations, and incompatible field/aggregation combinations when registering the dashboard, with HTTP 400 and a validation error. The existing rules for unknown schemas and duplicate dashboard names still apply.

### Generated dashboard result

`GET /dashboard/{name}` returns an `aggregate_table` view with one row per group. Keep the group value separate from the calculated values because the grouping field can also appear in `display_columns`, as `desk` does here.

For ingested rows with `SG` amounts of `1000` and `1500.5`, and one `HK` amount of `3000`, the view result is:

```json
{
  "type": "aggregate_table",
  "aggregate_column": "desk",
  "display_columns": {
    "amount": { "aggregation": "sum" },
    "desk": { "aggregation": "count" }
  },
  "rows": [
    {
      "group_value": "SG",
      "values": { "amount": 2500.5, "desk": 2 }
    },
    {
      "group_value": "HK",
      "values": { "amount": 3000, "desk": 1 }
    }
  ]
}
```

## Version 3: Pandas-backed data storage and dashboard calculation

Keep the existing four endpoints and all Version 1 and Version 2 request and
response formats. Replace the per-schema list of row dictionaries with one
in-memory pandas `DataFrame` per registered schema. Use pandas for dashboard
projection, grouping, and aggregation.

Pandas is the in-process storage and calculation engine in this version. Data,
schemas, and dashboard configurations still reset when the Flask process
restarts; restart-safe persistence is outside Version 3.

### Data storage rules

1. Create an empty DataFrame when a schema is registered. Its columns must use
   schema declaration order and these nullable pandas dtypes:

   | API field type | pandas dtype |
   | --- | --- |
   | `string` | `string` |
   | `number` | `Float64` |
   | `integer` | `Int64` |
   | `boolean` | `boolean` |

2. Pydantic remains the source of truth for request validation. Only construct
   and append a DataFrame after every row in the ingestion batch has passed the
   dynamic Pydantic row model. An invalid batch must not change stored data.
3. Cast an accepted batch to the registered schema's pandas dtypes before it is
   appended. Preserve schema column order and ingestion row order, and reset the
   DataFrame index after appending.
4. Optional omitted or JSON `null` values are stored as pandas missing values.
   Convert pandas missing values (`pd.NA`/`NaN`) back to JSON `null` in API
   responses.
5. Convert NumPy and pandas scalar results to native Python values before JSON
   serialization.
6. Repository reads must return a DataFrame copy so dashboard calculation cannot
   mutate stored rows. Repository mutation and snapshot creation remain protected
   by the existing lock.

### Dashboard calculation rules

1. A `table` view selects its configured DataFrame columns in configuration
   order and emits records in ingestion order.
2. A `summary` view uses the selected pandas Series. Missing values are excluded
   from all calculations. Preserve the existing empty-input results: `count` and
   `sum` return `0`; `average`, `min`, and `max` return `null`.
3. An `aggregate_table` view uses pandas grouping with sorting disabled and null
   groups enabled. Groups must remain in first-seen order, including the null
   group, and missing display values follow the same calculation rules as summary
   views.
4. `count` is valid for every supported field type and counts non-null values.
   `sum`, `average`, `min`, and `max` remain restricted to `number` and `integer`.
5. The generated dashboard JSON contract remains unchanged, so no frontend
   rendering change is required for Version 3.

### Dependency and test requirements

1. Add pandas as an application dependency and support pandas 2.x.
2. Retain all existing endpoint tests. Add coverage for schema-to-dtype mapping,
   missing-value serialization, DataFrame snapshot isolation, atomic ingestion,
   group ordering (including null), and native JSON scalar conversion.

### Deferred scaling work

Large table views still return every ingested row. Pagination, filtering,
sorting, row limits, disk persistence (for example Parquet), multi-process
coordination, and database-backed storage are separate API and architecture
changes and are not part of Version 3.
