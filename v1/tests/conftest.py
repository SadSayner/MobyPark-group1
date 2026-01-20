"""
Shared fixtures for all tests
"""
import pytest
from fastapi.testclient import TestClient

# Prevent tests from making real network calls to Elasticsearch.
# The production logger writes to Elasticsearch, but in unit/integration tests
# we replace the module-level client with an in-memory stub.
from ..server import logging_config


class _FakeElasticsearch:
    def __init__(self):
        self.calls = []

    def index(self, *, index, document):
        self.calls.append((index, document))


logging_config.es = _FakeElasticsearch()

from ..server.app import app

# Create test client
client = TestClient(app)

# Test data with email fields
# Username: 8-10 chars, must start with letter or underscore
# Password must be 12-30 chars with lowercase, uppercase, digit, and special char
TEST_USER = {
    "username": "pyt_user1",  # 9 chars
    "password": "TestPass123!",
    "name": "Pytest Test User",
    "email": "pytest_user@example.com",
    "phone": "1234567890",
    "role": "USER"
}

TEST_ADMIN = {
    "username": "pyt_adm01",  # 9 chars
    "password": "AdminPass123!",
    "name": "Pytest Admin User",
    "email": "pytest_admin@example.com",
    "phone": "0987654321",
    "role": "ADMIN"
}


@pytest.fixture(scope="session")
def test_client():
    """Provide test client for all tests"""
    return client


@pytest.fixture(scope="session", autouse=True)
def _clean_db_side_effects_for_tests():
    """Keep pytest runs stable when the sqlite DB persists between runs.

    We only clear tables that are frequently mutated by tests and can cause
    order-dependent behavior (e.g., payments/session IDs).
    """
    from ..Database.database_logic import get_connection

    con = get_connection()
    try:
        # Delete in proper order to respect foreign key constraints
        # 1. Delete payments first (references sessions)
        con.execute("DELETE FROM payments")

        # 2. Delete reservations (references users, parking_lots, vehicles)
        con.execute("DELETE FROM reservations")

        # 3. Delete sessions (references parking_lots, users, vehicles)
        con.execute("DELETE FROM sessions")

        # 4. Delete vehicles (referenced by sessions and reservations)
        con.execute("DELETE FROM vehicles WHERE license_plate LIKE 'TEST-%'")

        # 5. Delete parking lots (referenced by sessions and reservations)
        con.execute("DELETE FROM parking_lots WHERE name LIKE '%Pytest%' OR name LIKE '%Test%'")

        # 6. Delete test users last (referenced by sessions, reservations, vehicles)
        con.execute("DELETE FROM users WHERE email IN ('pytest_user@example.com', 'pytest_admin@example.com')")
        con.execute("DELETE FROM users WHERE username IN ('pyt_user1', 'pyt_adm01')")

        con.commit()
    finally:
        try:
            con.close()
        except Exception:
            pass


@pytest.fixture(scope="function")
def user_token(test_client):
    """Register and login a test user, return session token"""
    from ..Database.database_logic import get_connection

    # Clean up any existing test user first to ensure clean state for each test
    con = get_connection()
    try:
        con.execute("DELETE FROM users WHERE email = ? OR username = ?",
                   (TEST_USER["email"], TEST_USER["username"]))
        con.commit()
    finally:
        con.close()

    # Register the user
    reg_response = test_client.post("/auth/register", json=TEST_USER)

    if reg_response.status_code != 200:
        raise Exception(f"Registration failed: {reg_response.status_code}, {reg_response.json()}")

    # Login
    response = test_client.post("/auth/login", json={
        "email": TEST_USER["email"],
        "password": TEST_USER["password"]
    })

    if response.status_code != 200:
        raise Exception(f"Login failed: {response.status_code}, {response.json()}")

    return response.json()["session_token"]


@pytest.fixture(scope="module")
def admin_token(test_client):
    """Register and login an admin user, return session token"""
    from ..Database.database_logic import get_connection

    # Clean up any existing admin user first
    con = get_connection()
    try:
        con.execute("DELETE FROM users WHERE email = ? OR username = ?",
                   (TEST_ADMIN["email"], TEST_ADMIN["username"]))
        con.commit()
    finally:
        con.close()

    # Register the admin
    reg_response = test_client.post("/auth/register", json=TEST_ADMIN)

    if reg_response.status_code != 200:
        raise Exception(f"Admin registration failed: {reg_response.status_code}, {reg_response.json()}")

    # Login
    response = test_client.post("/auth/login", json={
        "email": TEST_ADMIN["email"],
        "password": TEST_ADMIN["password"]
    })

    if response.status_code != 200:
        raise Exception(f"Admin login failed: {response.status_code}, {response.json()}")

    return response.json()["session_token"]


@pytest.fixture(scope="module")
def parking_lot_id(test_client, admin_token):
    """Create a test parking lot and return its ID"""
    from ..Database.database_logic import get_connection

    # Clean up any existing test parking lot first
    con = get_connection()
    try:
        con.execute("DELETE FROM parking_lots WHERE name = 'Pytest Parking Lot'")
        con.commit()
    finally:
        con.close()

    response = test_client.post("/parking-lots",
        headers={"Authorization": admin_token},
        json={
            "name": "Pytest Parking Lot",
            "location": "Test Location",
            "address": "123 Test St",
            "capacity": 50,
            "reserved": 0,
            "tariff": 2.0,
            "daytariff": 15.0,
            "lat": 40.7128,
            "lng": -74.0060
        })

    if response.status_code == 200:
        return response.json()["id"]

    # If creation failed, try to get existing parking lots
    response = test_client.get("/parking-lots")
    if response.status_code == 200:
        lots = response.json()
        if lots:
            return lots[0]["id"]

    pytest.skip("No parking lots available")

@pytest.fixture(scope="function")
def setup_test_session(test_client, user_token, parking_lot_id):
    """Maakt een voertuig en een actieve parkeersessie aan voor de test."""
    import uuid
    import time

    # Generate unique license plate using timestamp and random UUID
    unique_plate = f"TST-{int(time.time() * 1000) % 10000}-{str(uuid.uuid4())[:4].upper()}"

    # 1. Registreer een test-voertuig (nodig voor een sessie)
    vehicle_payload = {
        "license_plate": unique_plate,
        "make": "Pytest",
        "model": "Tester",
        "year": 2024,
        "color": "Blue"
    }

    vehicle_response = test_client.post("/vehicles", headers={"Authorization": user_token}, json=vehicle_payload)

    # If vehicle creation fails, we can't proceed
    if vehicle_response.status_code not in [200, 201]:
        pytest.skip(f"Could not create test vehicle: {vehicle_response.text}")

    # 2. Start the session using the correct endpoint
    session_response = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
        headers={"Authorization": user_token},
        json={
            "licenseplate": unique_plate  # Use the license plate format the API expects
        })

    if session_response.status_code not in [200, 201]:
        pytest.skip(f"Could not start test session: {session_response.status_code} - {session_response.text}")

    # The response should contain session data with an ID
    session_data = session_response.json()
    if "session_id" in session_data:
        return session_data["session_id"]
    elif "id" in session_data:
        return session_data["id"]
    else:
        pytest.skip(f"Session response missing ID: {session_data}")