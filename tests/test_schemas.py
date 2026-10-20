"""Schema registration API tests."""

from tests.conftest import TRADE_SCHEMA


def test_registers_valid_schema(client):
    response = client.post("/schema", json=TRADE_SCHEMA)

    assert response.status_code == 201
    assert response.get_json() == {"name": "trade", "fields": 5}


def test_rejects_duplicate_schema(client):
    assert client.post("/schema", json=TRADE_SCHEMA).status_code == 201

    response = client.post("/schema", json=TRADE_SCHEMA)

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "SCHEMA_ALREADY_EXISTS"


def test_rejects_duplicate_field_names(client):
    payload = {
        "name": "duplicate-fields",
        "fields": [
            {"name": "id", "type": "string"},
            {"name": "id", "type": "integer"},
        ],
    }

    response = client.post("/schema", json=payload)

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_rejects_unsupported_field_type(client):
    payload = {
        "name": "bad-type",
        "fields": [{"name": "createdAt", "type": "date"}],
    }

    response = client.post("/schema", json=payload)

    assert response.status_code == 400
    details = response.get_json()["error"]["details"]
    assert details[0]["location"] == ["fields", 0, "type"]


def test_rejects_numeric_aggregation_on_string_field(client):
    payload = {
        "name": "bad-aggregation",
        "fields": [
            {"name": "status", "type": "string", "aggregation": "sum"}
        ],
    }

    response = client.post("/schema", json=payload)

    assert response.status_code == 400
    assert "requires a numeric field" in response.get_json()["error"]["details"][0]["message"]


def test_requires_json_content_type(client):
    response = client.post("/schema", data="not-json", content_type="text/plain")

    assert response.status_code == 415
    assert response.get_json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"

