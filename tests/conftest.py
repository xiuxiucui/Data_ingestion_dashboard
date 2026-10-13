"""Shared pytest fixtures and API helpers."""

from __future__ import annotations

import pytest

from backend.app import create_app
from backend.storage import InMemoryRepository


TRADE_SCHEMA = {
    "name": "trade",
    "fields": [
        {"name": "tradeId", "type": "string", "required": True},
        {
            "name": "amount",
            "type": "number",
            "required": True,
            "aggregation": "sum",
        },
        {"name": "status", "type": "string"},
        {"name": "settled", "type": "boolean"},
    ],
}


@pytest.fixture()
def repository():
    return InMemoryRepository()


@pytest.fixture()
def app(repository):
    application = create_app(repository)
    application.config.update(TESTING=True)
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def registered_trade(client):
    response = client.post("/schema", json=TRADE_SCHEMA)
    assert response.status_code == 201
    return TRADE_SCHEMA

