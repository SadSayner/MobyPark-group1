import random


def _register_and_login(test_client):
    rand_id = random.randint(100000000, 999999999)
    username = f"c{rand_id:09d}"  # exactly 10 chars, starts with letter
    password = "Password123!"  # meets complexity constraints used elsewhere

    reg = test_client.post(
        "/auth/register",
        json={
            "username": username,
            "password": password,
            "name": "Coverage User",
            "email": f"cov{rand_id}@example.com",
            "phone": "1234567890",
            "role": "USER",
        },
    )
    assert reg.status_code in (200, 409)

    login = test_client.post(
        "/auth/login",
        json={
            "username": username,
            "password": password,
        },
    )
    assert login.status_code == 200
    return username, login.json()["session_token"]


def test_root_endpoint_works(test_client):
    resp = test_client.get("/")
    assert resp.status_code == 200


def test_billing_endpoints_accessible(test_client, user_token, admin_token):
    import v1.tests.conftest as conf

    # user billing
    resp = test_client.get("/billing", headers={"Authorization": user_token})
    assert resp.status_code == 200

    # admin billing for a specific user
    resp = test_client.get(
        f"/billing/{conf.TEST_USER['username']}",
        headers={"Authorization": admin_token},
    )
    assert resp.status_code == 200


def test_admin_can_list_user_payments(test_client, admin_token):
    import v1.tests.conftest as conf

    resp = test_client.get(
        f"/payments/user/{conf.TEST_USER['username']}",
        headers={"Authorization": admin_token},
    )
    assert resp.status_code == 200


def test_admin_can_refund_linked_session(test_client, admin_token, parking_lot_id):
    # Create a session for an isolated user, then refund that session.
    _username, token = _register_and_login(test_client)

    start = test_client.post(
        f"/parking-lots/{parking_lot_id}/sessions/start",
        headers={"Authorization": token},
        json={"licenseplate": "RFND-001"},
    )
    assert start.status_code == 200
    session_id = start.json().get("id")
    assert session_id

    resp = test_client.post(
        "/payments/refund",
        headers={"Authorization": admin_token},
        json={
            "amount": 2.5,
            "parkingsession_id": session_id,
            "payment_method": "refund",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "Success"
    assert data.get("payment", {}).get("amount") == -2.5


def test_user_can_complete_payment_transaction(test_client, parking_lot_id):
    # Create session + payment for an isolated user so we don't mutate shared fixtures.
    _username, token = _register_and_login(test_client)

    start = test_client.post(
        f"/parking-lots/{parking_lot_id}/sessions/start",
        headers={"Authorization": token},
        json={"licenseplate": "PAY-001"},
    )
    assert start.status_code == 200
    session_id = start.json().get("id")
    assert session_id

    create = test_client.post(
        "/payments",
        headers={"Authorization": token},
        json={
            "amount": 1.0,
            "session_id": session_id,
            "payment_method": "ideal",
        },
    )
    assert create.status_code == 200
    payment = create.json().get("payment") or {}

    transaction_id = payment.get("transaction")
    validation_hash = payment.get("hash")
    assert transaction_id
    assert validation_hash

    complete = test_client.put(
        f"/payments/{transaction_id}",
        headers={"Authorization": token},
        json={
            "amount": 1.0,
            "t_data": {
                "t_date": "01-01-2026 00:00:00",
                "t_method": "ideal",
                "t_issuer": "pytest",
                "t_bank": "pytest",
            },
            "validation": validation_hash,
        },
    )
    assert complete.status_code == 200
    body = complete.json()
    assert body.get("status") == "Success"
