I would like you to implement a Flast backend app, for data ingestion with 4 API end points. the example input is listed at the end of this file

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