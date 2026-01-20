def test_log_event_indexes_to_elasticsearch_when_enabled(monkeypatch):
    import v1.server.logging_config as logging_config

    calls = []

    class FakeES:
        def index(self, *, index, document):
            calls.append((index, document))

    # Patch the module-level Elasticsearch client.
    monkeypatch.setattr(logging_config, "es", FakeES())

    logging_config.log_event(level="WARNING", event="unit_test", message="hello", foo="bar")

    # Original implementation indexes twice.
    assert len(calls) == 2
    index_name, doc = calls[0]
    assert index_name == "fastapi-v1-logs"
    assert doc.get("level") == "WARNING"
    assert doc.get("event") == "unit_test"
    assert doc.get("message") == "hello"
    assert doc.get("service") == "fastapi-v1"
    assert doc.get("foo") == "bar"
    assert "@timestamp" in doc
    assert "traceback" in doc


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
