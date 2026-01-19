import os
import importlib

import pytest


def test_log_event_indexes_to_elasticsearch_when_enabled(monkeypatch):
    # Import module fresh so our monkeypatching applies cleanly.
    import v1.server.logging_config as logging_config

    calls = []

    class FakeES:
        def __init__(self, url):
            self.url = url

        def index(self, *, index, document):
            calls.append((index, document))

    # Ensure logging is enabled and uses our fake client.
    monkeypatch.setenv("MOBYPARK_DISABLE_ELASTIC_LOGS", "0")
    monkeypatch.setenv("MOBYPARK_ELASTIC_URL", "http://fake-es:9200")
    monkeypatch.setattr(logging_config, "Elasticsearch", FakeES)
    monkeypatch.setattr(logging_config, "_ES_CLIENT", None)

    logging_config.log_event(level="WARNING", event="unit_test", message="hello", foo="bar")

    assert len(calls) == 1
    index_name, doc = calls[0]
    assert index_name == "fastapi-v1-logs"
    assert doc.get("level") == "WARNING"
    assert doc.get("event") == "unit_test"
    assert doc.get("message") == "hello"
    assert doc.get("service") == "fastapi-v1"
    assert doc.get("foo") == "bar"
    assert "@timestamp" in doc
    assert "traceback" in doc


def test_log_event_does_not_require_elasticsearch_when_disabled(monkeypatch, capsys):
    import v1.server.logging_config as logging_config

    monkeypatch.setenv("MOBYPARK_DISABLE_ELASTIC_LOGS", "1")
    monkeypatch.setattr(logging_config, "_ES_CLIENT", None)

    logging_config.log_event(level="WARNING", event="unit_test", message="hello")

    out = capsys.readouterr().out
    assert "[WARNING]" in out
    assert "unit_test" in out


def test_payments_logs_when_linked_session_not_found(monkeypatch, test_client, user_token):
    # Patch the router-local log_event used by the endpoint.
    import v1.server.routers.payments as payments_router

    logged = []

    def fake_log_event(*args, **kwargs):
        logged.append((args, kwargs))

    monkeypatch.setattr(payments_router, "log_event", fake_log_event)

    response = test_client.post(
        "/payments",
        headers={"Authorization": user_token},
        json={
            "session_id": 999999,
            "amount": 10.0,
            "payment_method": "credit_card",
        },
    )

    assert response.status_code == 404
    assert any(k.get("event") == "payment_create_failed" and k.get("message") == "linked_session_not_found" for _a, k in logged)
