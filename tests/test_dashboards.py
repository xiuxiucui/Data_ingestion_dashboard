"""Dashboard configuration and generation tests."""


DASHBOARD = {
    "name": "trade-dashboard",
    "schema": "trade",
    "views": [
        {"type": "summary", "field": "amount", "aggregation": "sum"},
        {
            "type": "table",
            "columns": ["tradeId", "amount", "status"],
        },
    ],
}


def test_registers_dashboard(client, registered_trade):
    response = client.post("/dashboard", json=DASHBOARD)

    assert response.status_code == 201
    assert response.get_json() == {
        "name": "trade-dashboard",
        "schema": "trade",
        "views": 2,
    }


def test_rejects_unknown_schema(client):
    response = client.post(
        "/dashboard",
        json={
            "name": "missing-dashboard",
            "schema": "missing",
            "views": [{"type": "table", "columns": ["id"]}],
        },
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "SCHEMA_NOT_FOUND"


def test_rejects_unknown_columns_and_incompatible_aggregation(client, registered_trade):
    payload = {
        "name": "invalid-dashboard",
        "schema": "trade",
        "views": [
            {"type": "summary", "field": "status", "aggregation": "sum"},
            {"type": "table", "columns": ["tradeId", "missing"]},
        ],
    }

    response = client.post("/dashboard", json=payload)

    assert response.status_code == 400
    details = response.get_json()["error"]["details"]
    assert {item["type"] for item in details} == {
        "incompatible_aggregation",
        "unknown_field",
    }


def test_rejects_duplicate_dashboard(client, registered_trade):
    assert client.post("/dashboard", json=DASHBOARD).status_code == 201

    response = client.post("/dashboard", json=DASHBOARD)

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "DASHBOARD_ALREADY_EXISTS"


def test_generates_summary_and_table_views(client, registered_trade):
    client.post(
        "/ingest",
        json={
            "schema": "trade",
            "rows": [
                {"tradeId": "T001", "amount": 1000, "status": "OPEN"},
                {"tradeId": "T002", "amount": 250.5, "status": "CLOSED"},
            ],
        },
    )
    client.post("/dashboard", json=DASHBOARD)

    response = client.get("/dashboard/trade-dashboard")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["views"][0] == {
        "type": "summary",
        "field": "amount",
        "aggregation": "sum",
        "value": 1250.5,
    }
    assert payload["views"][1]["rows"] == [
        {"tradeId": "T001", "amount": 1000, "status": "OPEN"},
        {"tradeId": "T002", "amount": 250.5, "status": "CLOSED"},
    ]


def test_generates_aggregate_table_view(client, registered_trade):
    client.post(
        "/ingest",
        json={
            "schema": "trade",
            "rows": [
                {"tradeId": "T001", "amount": 1000, "desk": "SG"},
                {"tradeId": "T002", "amount": 1500.5, "desk": "SG"},
                {"tradeId": "T003", "amount": 3000, "desk": "HK"},
                {"tradeId": "T004", "amount": 500, "desk": None},
            ],
        },
    )
    dashboard = {
        "name": "desk-dashboard",
        "schema": "trade",
        "views": [
            {
                "type": "aggregate_table",
                "aggregate_column": "desk",
                "display_columns": {
                    "amount": {"aggregation": "sum"},
                    "desk": {"aggregation": "count"},
                },
            }
        ],
    }

    assert client.post("/dashboard", json=dashboard).status_code == 201
    response = client.get("/dashboard/desk-dashboard")

    assert response.status_code == 200
    assert response.get_json()["views"][0] == {
        "type": "aggregate_table",
        "aggregate_column": "desk",
        "display_columns": {
            "amount": {"aggregation": "sum"},
            "desk": {"aggregation": "count"},
        },
        "rows": [
            {"group_value": "SG", "values": {"amount": 2500.5, "desk": 2}},
            {"group_value": "HK", "values": {"amount": 3000, "desk": 1}},
            {"group_value": None, "values": {"amount": 500, "desk": 0}},
        ],
    }


def test_rejects_invalid_aggregate_table_fields(client, registered_trade):
    response = client.post(
        "/dashboard",
        json={
            "name": "invalid-aggregate-dashboard",
            "schema": "trade",
            "views": [
                {
                    "type": "aggregate_table",
                    "aggregate_column": "missing_group",
                    "display_columns": {
                        "missing_value": {"aggregation": "count"},
                        "status": {"aggregation": "sum"},
                    },
                }
            ],
        },
    )

    assert response.status_code == 400
    details = response.get_json()["error"]["details"]
    assert [detail["type"] for detail in details] == [
        "unknown_field",
        "unknown_field",
        "incompatible_aggregation",
    ]


def test_aggregate_table_returns_empty_rows_without_ingested_data(
    client,
    registered_trade,
):
    response = client.post(
        "/dashboard",
        json={
            "name": "empty-aggregate-dashboard",
            "schema": "trade",
            "views": [
                {
                    "type": "aggregate_table",
                    "aggregate_column": "desk",
                    "display_columns": {
                        "amount": {"aggregation": "average"},
                    },
                }
            ],
        },
    )
    assert response.status_code == 201

    generated = client.get("/dashboard/empty-aggregate-dashboard")

    assert generated.status_code == 200
    assert generated.get_json()["views"][0]["rows"] == []


def test_returns_not_found_for_unknown_dashboard(client):
    response = client.get("/dashboard/missing")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "DASHBOARD_NOT_FOUND"

