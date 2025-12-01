"""
Pytest test suite for MobyPark API
Run with: pytest test_endpoints.py -v
Or: pytest test_endpoints.py -v -s  (to see print statements)
"""
import pytest
from fastapi.testclient import TestClient
from server.app import app

# Create test client
client = TestClient(app)

# Test data
TEST_USER = {
    "username": "pytest_user",
    "password": "testpass123",
    "name": "Pytest Test User",
    "role": "USER"
}

TEST_ADMIN = {
    "username": "pytest_admin",
    "password": "adminpass123",
    "name": "Pytest Admin User",
    "role": "ADMIN"
}

# Fixtures to store data across tests
@pytest.fixture(scope="module")
def user_token():
    """Register and login a test user, return session token"""
    # Try to register (might fail if already exists)
    client.post("/register", json=TEST_USER)

    # Login
    response = client.post("/login", json={
        "username": TEST_USER["username"],
        "password": TEST_USER["password"]
    })
    assert response.status_code == 200
    return response.json()["session_token"]

@pytest.fixture(scope="module")
def admin_token():
    """Register and login an admin user, return session token"""
    # Try to register (might fail if already exists)
    client.post("/register", json=TEST_ADMIN)

    # Login
    response = client.post("/login", json={
        "username": TEST_ADMIN["username"],
        "password": TEST_ADMIN["password"]
    })
    assert response.status_code == 200
    return response.json()["session_token"]

@pytest.fixture(scope="module")
def parking_lot_id(admin_token):
    """Create a test parking lot"""
    response = client.post("/parking-lots",
        headers={"Authorization": admin_token},
        json={
            "name": "Pytest Parking Lot",
            "location": "Test Location",
            "address": "123 Test St",
            "capacity": 50,
            "tariff": 2.0,
            "daytariff": 15.0,
            "lat": 40.7128,
            "lng": -74.0060
        })
    if response.status_code == 200:
        return response.json()["id"]
    # If creation failed, try to get existing parking lots
    response = client.get("/parking-lots")
    lots = response.json()
    if lots:
        return lots[0]["id"]
    pytest.skip("No parking lots available")


# ============================================
# Authentication Tests
# ============================================

class TestAuthentication:
    """Test authentication endpoints"""

    def test_register_new_user(self):
        """Test user registration"""
        response = client.post("/register", json={
            "username": f"newuser_{pytest.time.time()}",
            "password": "password123",
            "name": "New User",
            "role": "USER"
        })
        assert response.status_code == 200
        assert response.json()["message"] == "User created"

    def test_register_duplicate_user(self):
        """Test registering duplicate username"""
        # Register first time
        username = f"duplicate_{pytest.time.time()}"
        client.post("/register", json={
            "username": username,
            "password": "pass123",
            "name": "Test"
        })

        # Try to register again
        response = client.post("/register", json={
            "username": username,
            "password": "pass123",
            "name": "Test"
        })
        assert response.status_code == 409

    def test_login_success(self, user_token):
        """Test successful login"""
        assert user_token is not None
        assert len(user_token) > 0

    def test_login_invalid_credentials(self):
        """Test login with wrong password"""
        response = client.post("/login", json={
            "username": TEST_USER["username"],
            "password": "wrongpassword"
        })
        assert response.status_code == 401

    def test_get_profile(self, user_token):
        """Test getting user profile"""
        response = client.get("/profile", headers={"Authorization": user_token})
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == TEST_USER["username"]
        assert data["name"] == TEST_USER["name"]
        assert "password" not in data

    def test_get_profile_unauthorized(self):
        """Test getting profile without token"""
        response = client.get("/profile")
        assert response.status_code in [401, 422]

    def test_update_profile(self, user_token):
        """Test updating user profile"""
        response = client.put("/profile",
            headers={"Authorization": user_token},
            json={
                "email": "pytest@example.com",
                "phone": "+9876543210"
            })
        assert response.status_code == 200

    def test_logout(self, user_token):
        """Test logout"""
        response = client.get("/logout", headers={"Authorization": user_token})
        assert response.status_code == 200


# ============================================
# Vehicle Tests
# ============================================

class TestVehicles:
    """Test vehicle endpoints"""

    def test_create_vehicle(self, user_token):
        """Test creating a vehicle"""
        response = client.post("/vehicles",
            headers={"Authorization": user_token},
            json={
                "name": "Pytest Car",
                "license_plate": "PYTEST-001"
            })
        assert response.status_code == 200
        assert response.json()["status"] == "Success"
        assert response.json()["vehicle"]["licenseplate"] == "PYTEST-001"

    def test_create_vehicle_duplicate(self, user_token):
        """Test creating duplicate vehicle"""
        # Create first vehicle
        client.post("/vehicles",
            headers={"Authorization": user_token},
            json={"name": "Test", "license_plate": "DUP-123"})

        # Try to create duplicate
        response = client.post("/vehicles",
            headers={"Authorization": user_token},
            json={"name": "Test", "license_plate": "DUP-123"})
        assert response.status_code == 400

    def test_list_vehicles(self, user_token):
        """Test listing user's vehicles"""
        response = client.get("/vehicles", headers={"Authorization": user_token})
        assert response.status_code == 200
        assert isinstance(response.json(), dict)

    def test_update_vehicle(self, user_token):
        """Test updating a vehicle"""
        # First create a vehicle
        client.post("/vehicles",
            headers={"Authorization": user_token},
            json={"name": "Original", "license_plate": "UPD-001"})

        # Update it
        response = client.put("/vehicles/UPD-001",
            headers={"Authorization": user_token},
            json={"name": "Updated Name", "license_plate": "UPD-001"})
        assert response.status_code == 200
        assert response.json()["vehicle"]["name"] == "Updated Name"

    def test_delete_vehicle(self, user_token):
        """Test deleting a vehicle"""
        # Create vehicle
        client.post("/vehicles",
            headers={"Authorization": user_token},
            json={"name": "Delete Me", "license_plate": "DEL-001"})

        # Delete it
        response = client.delete("/vehicles/DEL-001",
            headers={"Authorization": user_token})
        assert response.status_code == 200


# ============================================
# Parking Lot Tests
# ============================================

class TestParkingLots:
    """Test parking lot endpoints"""

    def test_list_parking_lots(self):
        """Test listing all parking lots"""
        response = client.get("/parking-lots")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_parking_lot_detail(self, parking_lot_id):
        """Test getting specific parking lot"""
        response = client.get(f"/parking-lots/{parking_lot_id}")
        assert response.status_code == 200
        assert response.json()["id"] == parking_lot_id

    def test_create_parking_lot_unauthorized(self, user_token):
        """Test creating parking lot as non-admin"""
        response = client.post("/parking-lots",
            headers={"Authorization": user_token},
            json={"name": "Test", "location": "Test"})
        assert response.status_code == 403

    def test_create_parking_lot_admin(self, admin_token):
        """Test creating parking lot as admin"""
        response = client.post("/parking-lots",
            headers={"Authorization": admin_token},
            json={
                "name": "Admin Parking",
                "location": "Admin Location",
                "capacity": 100,
                "tariff": 3.0,
                "daytariff": 25.0
            })
        assert response.status_code == 200


# ============================================
# Parking Session Tests
# ============================================

class TestParkingSessions:
    """Test parking session endpoints"""

    def test_start_session(self, user_token, parking_lot_id):
        """Test starting a parking session"""
        response = client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            headers={"Authorization": user_token},
            json={"licenseplate": "SESSION-001"})
        assert response.status_code == 200
        assert "session_id" in response.json()["session"]

    def test_stop_session(self, user_token, parking_lot_id):
        """Test stopping a parking session"""
        # Start session
        start_response = client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            headers={"Authorization": user_token},
            json={"licenseplate": "SESSION-002"})
        assert start_response.status_code == 200

        # Stop session
        stop_response = client.post(f"/parking-lots/{parking_lot_id}/sessions/stop",
            headers={"Authorization": user_token},
            json={"licenseplate": "SESSION-002"})
        assert stop_response.status_code == 200

    def test_list_sessions(self, user_token, parking_lot_id):
        """Test listing sessions for a parking lot"""
        response = client.get(f"/parking-lots/{parking_lot_id}/sessions",
            headers={"Authorization": user_token})
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# ============================================
# Payment Tests
# ============================================

class TestPayments:
    """Test payment endpoints"""

    def test_create_payment(self, user_token, parking_lot_id):
        """Test creating a payment"""
        # Start and stop a session first
        client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            headers={"Authorization": user_token},
            json={"licenseplate": "PAY-001"})
        stop_resp = client.post(f"/parking-lots/{parking_lot_id}/sessions/stop",
            headers={"Authorization": user_token},
            json={"licenseplate": "PAY-001"})

        session_id = stop_resp.json()["id"]

        # Create payment
        response = client.post("/payments",
            headers={"Authorization": user_token},
            json={
                "amount": 5.50,
                "parkingsession_id": str(session_id)
            })
        assert response.status_code == 200
        assert response.json()["status"] == "Success"

    def test_list_payments(self, user_token):
        """Test listing user's payments"""
        response = client.get("/payments", headers={"Authorization": user_token})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_billing(self, user_token):
        """Test getting billing information"""
        response = client.get("/billing", headers={"Authorization": user_token})
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# ============================================
# Reservation Tests
# ============================================

class TestReservations:
    """Test reservation endpoints"""

    def test_create_reservation(self, user_token, parking_lot_id):
        """Test creating a reservation"""
        response = client.post("/reservations",
            headers={"Authorization": user_token},
            json={
                "licenseplate": "RES-001",
                "startdate": "15-12-2025 09:00:00",
                "enddate": "15-12-2025 18:00:00",
                "parkinglot": str(parking_lot_id)
            })
        assert response.status_code == 200
        assert response.json()["status"] == "Success"

    def test_get_reservation(self, user_token, parking_lot_id):
        """Test getting reservation details"""
        # Create reservation
        create_resp = client.post("/reservations",
            headers={"Authorization": user_token},
            json={
                "licenseplate": "RES-002",
                "startdate": "16-12-2025 09:00:00",
                "enddate": "16-12-2025 18:00:00",
                "parkinglot": str(parking_lot_id)
            })
        reservation_id = create_resp.json()["reservation"]["id"]

        # Get reservation
        response = client.get(f"/reservations/{reservation_id}",
            headers={"Authorization": user_token})
        assert response.status_code == 200
        assert response.json()["id"] == reservation_id

    def test_update_reservation(self, user_token, parking_lot_id):
        """Test updating a reservation"""
        # Create reservation
        create_resp = client.post("/reservations",
            headers={"Authorization": user_token},
            json={
                "licenseplate": "RES-003",
                "startdate": "17-12-2025 09:00:00",
                "enddate": "17-12-2025 18:00:00",
                "parkinglot": str(parking_lot_id)
            })
        reservation_id = create_resp.json()["reservation"]["id"]

        # Update reservation
        response = client.put(f"/reservations/{reservation_id}",
            headers={"Authorization": user_token},
            json={
                "licenseplate": "RES-003",
                "startdate": "18-12-2025 10:00:00",
                "enddate": "18-12-2025 19:00:00",
                "parkinglot": str(parking_lot_id)
            })
        assert response.status_code == 200

    def test_delete_reservation(self, user_token, parking_lot_id):
        """Test deleting a reservation"""
        # Create reservation
        create_resp = client.post("/reservations",
            headers={"Authorization": user_token},
            json={
                "licenseplate": "RES-004",
                "startdate": "19-12-2025 09:00:00",
                "enddate": "19-12-2025 18:00:00",
                "parkinglot": str(parking_lot_id)
            })
        reservation_id = create_resp.json()["reservation"]["id"]

        # Delete reservation
        response = client.delete(f"/reservations/{reservation_id}",
            headers={"Authorization": user_token})
        assert response.status_code == 200


# ============================================
# Run all tests
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
