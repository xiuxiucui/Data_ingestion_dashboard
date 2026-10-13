"""Data ingestion API tests."""


def test_ingests_valid_rows(client, registered_trade):
    response = client.post(
        "/ingest",
        json={
            "schema": "trade",
            "rows": [
                {"tradeId": "T001", "amount": 1000, "status": "OPEN"},
                {
                    "tradeId": "T002",
                    "amount": 125.5,
                    "status": "CLOSED",
                    "settled": True,
                },
            ],
        },
    )

    assert response.status_code == 201
    assert response.get_json() == {
        "schema": "trade",
        "accepted": 2,
        "totalRows": 2,
    }


def test_rejects_unknown_schema(client):
    response = client.post(
        "/ingest",
        json={"schema": "missing", "rows": [{"id": "1"}]},
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "SCHEMA_NOT_FOUND"


def test_rejects_missing_required_field(client, registered_trade):
    response = client.post(
        "/ingest",
        json={"schema": "trade", "rows": [{"tradeId": "T001"}]},
    )

    assert response.status_code == 400
    details = response.get_json()["error"]["details"]
    assert any(item["location"] == ["rows", 0, "amount"] for item in details)


def test_rejects_unknown_fields_and_type_error(client, registered_trade):
    response = client.post(
        "/ingest",
        json={
            "schema": "trade",
            "rows": [
                {
                    "tradeId": "T001",
                    "amount": "1000",
                    "unexpected": "value",
                }
            ],
        },
    )

    assert response.status_code == 400
    locations = [item["location"] for item in response.get_json()["error"]["details"]]
    assert ["rows", 0, "amount", "int"] in locations
    assert ["rows", 0, "unexpected"] in locations


