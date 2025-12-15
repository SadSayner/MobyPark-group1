"""
Shared fixtures for all tests
"""
import pytest
from fastapi.testclient import TestClient
from ..server.app import app

# Create test client
client = TestClient(app)

# Test data with email fields
TEST_USER = {
    "username": "pytest_user",
    "password": "testpass123",
    "name": "Pytest Test User",
    "email": "pytest_user@example.com",
    "phone": "1234567890",
    "role": "USER"
}

TEST_ADMIN = {
    "username": "pytest_admin",
    "password": "adminpass123",
    "name": "Pytest Admin User",
    "email": "pytest_admin@example.com",
    "phone": "0987654321",
    "role": "ADMIN"
}


@pytest.fixture(scope="session")
def test_client():
    """Provide test client for all tests"""
    return client


@pytest.fixture(scope="module")
def user_token(test_client):
    """Register and login a test user, return session token"""
    # Try to register (might fail if already exists)
    test_client.post("/auth/register", json=TEST_USER)

    # Login
    response = test_client.post("/auth/login", json={
        "username": TEST_USER["username"],
        "password": TEST_USER["password"]
    })
    assert response.status_code == 200
    return response.json()["session_token"]


@pytest.fixture(scope="module")
def admin_token(test_client):
    """Register and login an admin user, return session token"""
    # Try to register (might fail if already exists)
    test_client.post("/auth/register", json=TEST_ADMIN)

    # Login
    response = test_client.post("/auth/login", json={
        "username": TEST_ADMIN["username"],
        "password": TEST_ADMIN["password"]
    })
    assert response.status_code == 200
    return response.json()["session_token"]


@pytest.fixture(scope="module")
def parking_lot_id(test_client, admin_token):
    """Create a test parking lot and return its ID"""
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
