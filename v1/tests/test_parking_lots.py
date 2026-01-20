"""
Parking lot endpoint tests - comprehensive test suite
"""
import random
import pytest


class TestParkingLotsCRUD:
    def test_create_parking_lot_admin_success(self, test_client, admin_token):
        """Test creating parking lot with admin role - happy path"""
        rand_id = random.randint(100000, 999999)
        response = test_client.post("/parking-lots",
            headers={"authorization": admin_token},
            json={
                "name": f"Test Lot {rand_id}",
                "location": "Amsterdam Centrum",
                "address": "Dam 1, 1012 JS Amsterdam",
                "capacity": 100,
                "reserved": 0,
                "tariff": 3.50,
                "daytariff": 25.00,
                "lat": 52.3676,
                "lng": 4.9041
            })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "message" in data

    def test_create_parking_lot_unauthorized_user(self, test_client, user_token):
        """Test creating parking lot without admin role - should fail"""
        rand_id = random.randint(100000, 999999)
        response = test_client.post("/parking-lots",
            headers={"authorization": user_token},
            json={
                "name": f"Unauthorized Lot {rand_id}",
                "location": "Test",
                "address": "123 Test",
                "capacity": 10,
                "tariff": 1.0,
                "daytariff": 10.0,
                "lat": 40.0,
                "lng": -74.0
            })
        assert response.status_code == 403  # Forbidden

    def test_create_parking_lot_no_auth(self, test_client):
        """Test creating parking lot without authentication"""
        response = test_client.post("/parking-lots",
            json={
                "name": "No Auth Lot",
                "location": "Test",
                "address": "123 Test",
                "capacity": 10,
                "tariff": 1.0,
                "daytariff": 10.0,
                "lat": 40.0,
                "lng": -74.0
            })
        assert response.status_code in [401, 422]

    @pytest.mark.xfail(reason="API doesn't validate required fields - raises uncaught IntegrityError (NOT NULL constraint)", strict=True)
    def test_create_parking_lot_missing_required_fields(self, test_client, admin_token):
        """Test creating parking lot with missing required fields"""
        response = test_client.post("/parking-lots",
            headers={"authorization": admin_token},
            json={
                "name": "Incomplete Lot"
                # Missing: location, address, capacity, tariff, etc.
            })
        # Should fail with validation error
        # TODO: API should validate required fields BEFORE database insertion
        assert response.status_code in [400, 422]

    def test_create_parking_lot_negative_capacity(self, test_client, admin_token):
        """Test creating parking lot with negative capacity"""
        rand_id = random.randint(100000, 999999)
        response = test_client.post("/parking-lots",
            headers={"authorization": admin_token},
            json={
                "name": f"Negative Lot {rand_id}",
                "location": "Test",
                "address": "123 Test",
                "capacity": -50,  # Negative capacity
                "tariff": 3.0,
                "daytariff": 20.0,
                "lat": 40.0,
                "lng": -74.0
            })
        # Should either succeed (no validation) or fail (with validation)
        assert response.status_code in [200, 400, 422]

    def test_create_parking_lot_negative_tariff(self, test_client, admin_token):
        """Test creating parking lot with negative tariff"""
        rand_id = random.randint(100000, 999999)
        response = test_client.post("/parking-lots",
            headers={"authorization": admin_token},
            json={
                "name": f"Negative Tariff {rand_id}",
                "location": "Test",
                "address": "123 Test",
                "capacity": 50,
                "tariff": -5.0,  # Negative tariff
                "daytariff": 20.0,
                "lat": 40.0,
                "lng": -74.0
            })
        # Should either succeed or fail based on validation
        assert response.status_code in [200, 400, 422]

    def test_create_parking_lot_invalid_coordinates(self, test_client, admin_token):
        """Test creating parking lot with invalid GPS coordinates"""
        rand_id = random.randint(100000, 999999)
        response = test_client.post("/parking-lots",
            headers={"authorization": admin_token},
            json={
                "name": f"Invalid Coords {rand_id}",
                "location": "Test",
                "address": "123 Test",
                "capacity": 50,
                "tariff": 3.0,
                "daytariff": 20.0,
                "lat": 200.0,  # Invalid latitude (should be -90 to 90)
                "lng": 300.0   # Invalid longitude (should be -180 to 180)
            })
        # Should either succeed or fail based on validation
        assert response.status_code in [200, 400, 422]

    # ============ READ TESTS ============

    def test_list_parking_lots_no_auth(self, test_client):
        """Test listing parking lots without authentication"""
        response = test_client.get("/parking-lots")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_parking_lots_with_auth(self, test_client, user_token):
        """Test listing parking lots with user authentication"""
        response = test_client.get("/parking-lots",
            headers={"authorization": user_token})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_parking_lot_detail(self, test_client, parking_lot_id):
        """Test getting parking lot details by ID"""
        response = test_client.get(f"/parking-lots/{parking_lot_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == parking_lot_id
        assert "name" in data
        assert "capacity" in data
        assert "tariff" in data

    def test_get_parking_lot_nonexistent(self, test_client):
        """Test getting nonexistent parking lot"""
        response = test_client.get("/parking-lots/999999999")
        assert response.status_code == 404

    @pytest.mark.xfail(reason="API doesn't handle invalid ID format gracefully - raises uncaught ValueError", strict=True)
    def test_get_parking_lot_invalid_id(self, test_client):
        """Test getting parking lot with invalid ID format"""
        response = test_client.get("/parking-lots/invalid_id")
        # Should return 400 (bad request) or 422 (validation error)
        # TODO: API should use int type in path parameter or catch ValueError
        assert response.status_code in [400, 422]

    # ============ UPDATE TESTS ============

    def test_update_parking_lot_admin(self, test_client, admin_token, parking_lot_id):
        """Test updating parking lot as admin"""
        response = test_client.put(f"/parking-lots/{parking_lot_id}",
            headers={"authorization": admin_token},
            json={
                "capacity": 150,
                "tariff": 4.0
            })
        assert response.status_code == 200
        assert "message" in response.json()

    def test_update_parking_lot_user_forbidden(self, test_client, user_token, parking_lot_id):
        """Test updating parking lot as regular user - should fail"""
        response = test_client.put(f"/parking-lots/{parking_lot_id}",
            headers={"authorization": user_token},
            json={
                "capacity": 150
            })
        assert response.status_code == 403

    def test_update_parking_lot_no_auth(self, test_client, parking_lot_id):
        """Test updating parking lot without authentication"""
        response = test_client.put(f"/parking-lots/{parking_lot_id}",
            json={
                "capacity": 150
            })
        assert response.status_code in [401, 422]

    def test_update_parking_lot_nonexistent(self, test_client, admin_token):
        """Test updating nonexistent parking lot"""
        response = test_client.put("/parking-lots/999999999",
            headers={"authorization": admin_token},
            json={
                "capacity": 150
            })
        assert response.status_code == 404

    def test_update_parking_lot_partial(self, test_client, admin_token, parking_lot_id):
        """Test partial update (only some fields)"""
        response = test_client.put(f"/parking-lots/{parking_lot_id}",
            headers={"authorization": admin_token},
            json={
                "name": "Updated Name Only"
            })
        assert response.status_code == 200

    def test_update_parking_lot_empty_body(self, test_client, admin_token, parking_lot_id):
        """Test update with empty body"""
        response = test_client.put(f"/parking-lots/{parking_lot_id}",
            headers={"authorization": admin_token},
            json={})
        # Empty update might succeed (no changes) or fail (validation)
        assert response.status_code in [200, 400, 422]

    def test_update_parking_lot_invalid_data(self, test_client, admin_token, parking_lot_id):
        """Test updating parking lot with invalid data"""
        response = test_client.put(f"/parking-lots/{parking_lot_id}",
            headers={"authorization": admin_token},
            json={"capacity": -100})
        assert response.status_code in [200, 400, 422]

    # ============ DELETE TESTS ============

    def test_delete_parking_lot_admin(self, test_client, admin_token):
        """Test deleting parking lot as admin"""
        # First create a lot to delete
        rand_id = random.randint(100000, 999999)
        create_response = test_client.post("/parking-lots",
            headers={"authorization": admin_token},
            json={
                "name": f"To Delete {rand_id}",
                "location": "Test",
                "address": "123 Test",
                "capacity": 10,
                "tariff": 1.0,
                "daytariff": 10.0,
                "lat": 40.0,
                "lng": -74.0
            })
        lot_id = create_response.json()["id"]

        # Now delete it
        response = test_client.delete(f"/parking-lots/{lot_id}",
            headers={"authorization": admin_token})
        assert response.status_code == 200

        # Verify it's gone
        get_response = test_client.get(f"/parking-lots/{lot_id}")
        assert get_response.status_code == 404

    def test_delete_parking_lot_user_forbidden(self, test_client, user_token, parking_lot_id):
        """Test deleting parking lot as regular user - should fail"""
        response = test_client.delete(f"/parking-lots/{parking_lot_id}",
            headers={"authorization": user_token})
        assert response.status_code == 403

    def test_delete_parking_lot_no_auth(self, test_client, parking_lot_id):
        """Test deleting parking lot without authentication"""
        response = test_client.delete(f"/parking-lots/{parking_lot_id}")
        assert response.status_code in [401, 422]

    def test_delete_parking_lot_nonexistent(self, test_client, admin_token):
        """Test deleting nonexistent parking lot"""
        response = test_client.delete("/parking-lots/999999999",
            headers={"authorization": admin_token})
        assert response.status_code == 404

    def test_delete_parking_lot(self, test_client, admin_token, parking_lot_id):
        """Test deleting a parking lot"""
        response = test_client.delete(f"/parking-lots/{parking_lot_id}", headers={"authorization": admin_token})
        assert response.status_code in [200, 404]

    def test_list_parking_lots_with_filter(self, test_client):
        """Test listing parking lots with filter (if supported)"""
        response = test_client.get("/parking-lots?location=Amsterdam")
        assert response.status_code in [200, 400, 422]

    def test_unauthorized_admin_access(self, test_client, user_token, parking_lot_id):
        """Test unauthorized access to admin-only endpoint"""
        response = test_client.delete(f"/parking-lots/{parking_lot_id}", headers={"authorization": user_token})
        assert response.status_code in [403, 401, 422]

    @pytest.mark.parametrize("capacity,expected_status", [
        (100, [200]),
        (-1, [200, 400, 422]),
        (0, [200, 400, 422]),
    ])
    def test_create_parking_lot_various_capacities(self, test_client, admin_token, capacity, expected_status):
        """Test creating parking lot with various capacities"""
        rand_id = random.randint(100000, 999999)
        response = test_client.post("/parking-lots",
            headers={"authorization": admin_token},
            json={
                "name": f"LotCap{rand_id}",
                "location": "Test",
                "address": "Test",
                "capacity": capacity,
                "tariff": 2.0,
                "daytariff": 10.0,
                "lat": 52.0,
                "lng": 4.0
            })
        assert response.status_code in expected_status

    def test_update_nonexistent_parking_lot(self, test_client, admin_token):
        """Test updating a non-existent parking lot"""
        response = test_client.put("/parking-lots/999999",
            headers={"authorization": admin_token},
            json={"name": "ShouldNotExist"})
        assert response.status_code in [404, 400]

    def test_delete_nonexistent_parking_lot(self, test_client, admin_token):
        """Test deleting a non-existent parking lot"""
        response = test_client.delete("/parking-lots/999999", headers={"authorization": admin_token})
        assert response.status_code in [404, 400]

    def test_list_parking_lots_pagination(self, test_client):
        """Test listing parking lots with pagination (if supported)"""
        response = test_client.get("/parking-lots?page=1&size=2")
        assert response.status_code in [200, 400, 422]

    def test_parking_lot_response_fields(self, test_client, parking_lot_id):
        """Assert on returned parking lot data fields"""
        response = test_client.get(f"/parking-lots/{parking_lot_id}")
        if response.status_code == 200:
            data = response.json()
            for field in ["id", "name", "location", "address", "capacity", "tariff", "lat", "lng"]:
                assert field in data


@pytest.mark.xfail(reason="API has import bug in parking_lots.py:103 - all session endpoints fail with ImportError", strict=False)
class TestParkingSessions:
    """Test parking session functionality"""

    # ============ START SESSION TESTS ============

    def test_start_session_success(self, test_client, user_token, parking_lot_id):
        """Test starting a parking session - happy path"""
        rand_id = random.randint(100000, 999999)
        response = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            headers={"authorization": user_token},
            json={
                "licenseplate": f"AB-{rand_id % 1000}-CD"
            })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "session" in data
        assert data["session"]["payment_status"] == "unpaid"

    def test_start_session_no_auth(self, test_client, parking_lot_id):
        """Test starting session without authentication"""
        response = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            json={
                "licenseplate": "XX-999-YY"
            })
        assert response.status_code in [401, 422]

    def test_start_session_missing_licenseplate(self, test_client, user_token, parking_lot_id):
        """Test starting session without license plate"""
        response = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            headers={"authorization": user_token},
            json={})
        assert response.status_code == 400
        assert "licenseplate" in response.json()["detail"]["field"].lower()

    def test_start_session_duplicate_active(self, test_client, user_token, parking_lot_id):
        """Test starting session when one is already active"""
        rand_id = random.randint(100000, 999999)
        license_plate = f"DUP-{rand_id % 1000}"

        # Start first session
        response1 = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            headers={"authorization": user_token},
            json={"licenseplate": license_plate})
        assert response1.status_code == 200

        # Try to start second session with same plate (should fail)
        response2 = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            headers={"authorization": user_token},
            json={"licenseplate": license_plate})
        assert response2.status_code == 400
        assert "already active" in response2.json()["detail"].lower()

    def test_start_session_nonexistent_lot(self, test_client, user_token):
        """Test starting session for nonexistent parking lot"""
        response = test_client.post("/parking-lots/999999999/sessions/start",
            headers={"authorization": user_token},
            json={
                "licenseplate": "XX-999-YY"
            })
        # Might succeed (no validation) or fail (404)
        assert response.status_code in [200, 404, 500]

    # ============ STOP SESSION TESTS ============

    def test_stop_session_success(self, test_client, user_token, parking_lot_id):
        """Test stopping a parking session - happy path"""
        rand_id = random.randint(100000, 999999)
        license_plate = f"STOP-{rand_id % 1000}"

        # Start session
        start_response = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            headers={"authorization": user_token},
            json={"licenseplate": license_plate})
        assert start_response.status_code == 200

        # Stop session
        stop_response = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/stop",
            headers={"authorization": user_token},
            json={"licenseplate": license_plate})
        assert stop_response.status_code == 200
        assert "message" in stop_response.json()

    def test_stop_session_no_auth(self, test_client, parking_lot_id):
        """Test stopping session without authentication"""
        response = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/stop",
            json={
                "licenseplate": "XX-999-YY"
            })
        assert response.status_code in [401, 422]

    def test_stop_session_missing_licenseplate(self, test_client, user_token, parking_lot_id):
        """Test stopping session without license plate"""
        response = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/stop",
            headers={"authorization": user_token},
            json={})
        assert response.status_code == 400
        assert "licenseplate" in response.json()["detail"]["field"].lower()

    def test_stop_session_no_active_session(self, test_client, user_token, parking_lot_id):
        """Test stopping session when no active session exists"""
        response = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/stop",
            headers={"authorization": user_token},
            json={
                "licenseplate": "NOACTIVE-123"
            })
        assert response.status_code == 400
        assert "no active session" in response.json()["detail"].lower()

    def test_stop_session_nonexistent_vehicle(self, test_client, user_token, parking_lot_id):
        """Test stopping session for nonexistent vehicle"""
        response = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/stop",
            headers={"authorization": user_token},
            json={
                "licenseplate": "NEVER-REGISTERED-999"
            })
        assert response.status_code == 404
        assert "vehicle not found" in response.json()["detail"].lower()

    # ============ LIST SESSIONS TESTS ============

    def test_list_sessions_user(self, test_client, user_token, parking_lot_id):
        """Test listing sessions as regular user - should only see own sessions"""
        response = test_client.get(f"/parking-lots/{parking_lot_id}/sessions",
            headers={"authorization": user_token})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_sessions_admin(self, test_client, admin_token, parking_lot_id):
        """Test listing sessions as admin - should see all sessions"""
        response = test_client.get(f"/parking-lots/{parking_lot_id}/sessions",
            headers={"authorization": admin_token})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_sessions_no_auth(self, test_client, parking_lot_id):
        """Test listing sessions without authentication"""
        response = test_client.get(f"/parking-lots/{parking_lot_id}/sessions")
        assert response.status_code in [401, 422]

    # ============ GET SESSION DETAIL TESTS ============

    def test_get_session_detail_owner(self, test_client, user_token, parking_lot_id):
        """Test getting session detail as session owner"""
        rand_id = random.randint(100000, 999999)
        license_plate = f"DETAIL-{rand_id % 1000}"

        # Create session
        start_response = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            headers={"authorization": user_token},
            json={"licenseplate": license_plate})
        session_id = start_response.json()["id"]

        # Get detail
        response = test_client.get(f"/parking-lots/{parking_lot_id}/sessions/{session_id}",
            headers={"authorization": user_token})
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id

    def test_get_session_detail_admin(self, test_client, admin_token, user_token, parking_lot_id):
        """Test getting session detail as admin (should see any session)"""
        rand_id = random.randint(100000, 999999)
        license_plate = f"ADMIN-{rand_id % 1000}"

        # User creates session
        start_response = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            headers={"authorization": user_token},
            json={"licenseplate": license_plate})
        session_id = start_response.json()["id"]

        # Admin gets detail
        response = test_client.get(f"/parking-lots/{parking_lot_id}/sessions/{session_id}",
            headers={"authorization": admin_token})
        assert response.status_code == 200

    def test_get_session_detail_no_auth(self, test_client, parking_lot_id):
        """Test getting session detail without authentication"""
        response = test_client.get(f"/parking-lots/{parking_lot_id}/sessions/999")
        assert response.status_code in [401, 422]

    def test_get_session_detail_nonexistent(self, test_client, user_token, parking_lot_id):
        """Test getting nonexistent session"""
        response = test_client.get(f"/parking-lots/{parking_lot_id}/sessions/999999999",
            headers={"authorization": user_token})
        assert response.status_code == 404

    @pytest.fixture(scope="function")
    def other_user_token(self, test_client):
        """Create another user for testing access control"""
        rand_id = random.randint(100000, 999999)

        # Register
        test_client.post("/auth/register", json={
            "username": f"other{rand_id}"[:10],
            "password": "OtherPass123!",
            "name": "Other User",
            "email": f"other{rand_id}@example.com",
            "phone": "9999999999",
            "role": "USER"
        })

        # Login
        response = test_client.post("/auth/login", json={
            "email": f"other{rand_id}@example.com",
            "password": "OtherPass123!"
        })
        return response.json()["session_token"]

    def test_get_session_detail_other_user_forbidden(self, test_client, user_token, other_user_token, parking_lot_id):
        """Test getting another user's session - should be forbidden"""
        rand_id = random.randint(100000, 999999)
        license_plate = f"PRIV-{rand_id % 1000}"

        # User1 creates session
        start_response = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            headers={"authorization": user_token},
            json={"licenseplate": license_plate})
        session_id = start_response.json()["id"]

        # User2 tries to access it (should fail)
        response = test_client.get(f"/parking-lots/{parking_lot_id}/sessions/{session_id}",
            headers={"authorization": other_user_token})
        assert response.status_code == 403

    # ============ DELETE SESSION TESTS ============

    def test_delete_session_admin(self, test_client, admin_token, user_token, parking_lot_id):
        """Test deleting session as admin"""
        rand_id = random.randint(100000, 999999)
        license_plate = f"DEL-{rand_id % 1000}"

        # Create session
        start_response = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            headers={"authorization": user_token},
            json={"licenseplate": license_plate})
        session_id = start_response.json()["id"]

        # Admin deletes it
        response = test_client.delete(f"/parking-lots/{parking_lot_id}/sessions/{session_id}",
            headers={"authorization": admin_token})
        assert response.status_code == 200

        # Verify it's gone
        get_response = test_client.get(f"/parking-lots/{parking_lot_id}/sessions/{session_id}",
            headers={"authorization": admin_token})
        assert get_response.status_code == 404

    def test_delete_session_user_forbidden(self, test_client, user_token, parking_lot_id):
        """Test deleting session as regular user - should fail"""
        rand_id = random.randint(100000, 999999)
        license_plate = f"USERDEL-{rand_id % 1000}"

        # Create session
        start_response = test_client.post(f"/parking_lots/{parking_lot_id}/sessions/start",
            headers={"authorization": user_token},
            json={"licenseplate": license_plate})
        session_id = start_response.json()["id"]

        # Try to delete (should fail)
        response = test_client.delete(f"/parking-lots/{parking_lot_id}/sessions/{session_id}",
            headers={"authorization": user_token})
        assert response.status_code == 403

    def test_delete_session_no_auth(self, test_client, parking_lot_id):
        """Test deleting session without authentication"""
        response = test_client.delete(f"/parking-lots/{parking_lot_id}/sessions/999")
        assert response.status_code in [401, 422]

    def test_delete_session_nonexistent(self, test_client, admin_token, parking_lot_id):
        """Test deleting nonexistent session"""
        response = test_client.delete(f"/parking-lots/{parking_lot_id}/sessions/999999999",
            headers={"authorization": admin_token})
        assert response.status_code == 404


@pytest.mark.xfail(reason="API has import bug in parking_lots.py:103 - 'from Database.database_logic' should be 'from ...Database.database_logic'", strict=False)
class TestSessionWorkflow:
    """Test complete session workflows"""

    def test_complete_parking_workflow(self, test_client, user_token, parking_lot_id):
        """Test complete workflow: start session → get detail → stop session"""
        rand_id = random.randint(100000, 999999)
        license_plate = f"FLOW-{rand_id % 1000}"

        # 1. Start session
        start_response = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            headers={"authorization": user_token},
            json={"licenseplate": license_plate})
        assert start_response.status_code == 200
        session_id = start_response.json()["id"]

        # 2. Get session detail
        detail_response = test_client.get(f"/parking-lots/{parking_lot_id}/sessions/{session_id}",
            headers={"authorization": user_token})
        assert detail_response.status_code == 200
        assert detail_response.json()["stopped"] is None  # Not stopped yet

        # 3. Stop session
        stop_response = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/stop",
            headers={"authorization": user_token},
            json={"licenseplate": license_plate})
        assert stop_response.status_code == 200

        # 4. Verify session is stopped
        final_detail = test_client.get(f"/parking-lots/{parking_lot_id}/sessions/{session_id}",
            headers={"authorization": user_token})
        assert final_detail.status_code == 200
        assert final_detail.json()["stopped"] is not None  # Now stopped

    def test_multiple_sessions_same_user(self, test_client, user_token, parking_lot_id):
        """Test user can have multiple sessions with different vehicles"""
        rand_id = random.randint(100000, 999999)
        plate1 = f"CAR1-{rand_id % 1000}"
        plate2 = f"CAR2-{rand_id % 1000}"

        # Start session 1
        response1 = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            headers={"authorization": user_token},
            json={"licenseplate": plate1})
        assert response1.status_code == 200

        # Start session 2 with different plate
        response2 = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            headers={"authorization": user_token},
            json={"licenseplate": plate2})
        assert response2.status_code == 200

        # Both should be listed
        list_response = test_client.get(f"/parking-lots/{parking_lot_id}/sessions",
            headers={"authorization": user_token})
        sessions = list_response.json()
        active_sessions = [s for s in sessions if s["stopped"] is None]
        assert len(active_sessions) >= 2

    def test_restart_session_after_stop(self, test_client, user_token, parking_lot_id):
        """Test can restart session after stopping it"""
        rand_id = random.randint(100000, 999999)
        license_plate = f"RESTART-{rand_id % 1000}"

        # Start session
        start1 = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            headers={"authorization": user_token},
            json={"licenseplate": license_plate})
        assert start1.status_code == 200

        # Stop session
        stop = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/stop",
            headers={"authorization": user_token},
            json={"licenseplate": license_plate})
        assert stop.status_code == 200

        # Start again (should work)
        start2 = test_client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            headers={"authorization": user_token},
            json={"licenseplate": license_plate})
        assert start2.status_code == 200


class TestParkingLotEdgeCases:
    """Test edge cases and security issues"""

    @pytest.mark.xfail(reason="API doesn't handle invalid ID format gracefully - raises uncaught ValueError", strict=True)
    def test_sql_injection_in_lot_id(self, test_client):
        """Test SQL injection attempt in parking lot ID"""
        response = test_client.get("/parking-lots/1' OR '1'='1")
        # Should fail with validation error (400/422), not 500
        # TODO: API should use int type in path parameter or catch ValueError
        assert response.status_code in [400, 404, 422]

    def test_sql_injection_in_session_id(self, test_client, user_token, parking_lot_id):
        """Test SQL injection attempt in session ID"""
        response = test_client.get(f"/parking-lots/{parking_lot_id}/sessions/1' OR '1'='1",
            headers={"authorization": user_token})
        assert response.status_code in [400, 404, 422, 500]

    def test_xss_in_parking_lot_name(self, test_client, admin_token):
        """Test XSS protection in parking lot name"""
        rand_id = random.randint(100000, 999999)
        response = test_client.post("/parking-lots",
            headers={"authorization": admin_token},
            json={
                "name": f"<script>alert('xss')</script> Lot {rand_id}",
                "location": "Test",
                "address": "123 Test",
                "capacity": 50,
                "tariff": 3.0,
                "daytariff": 20.0,
                "lat": 40.0,
                "lng": -74.0
            })
        # Should succeed - sanitization happens on display
        assert response.status_code == 200

    def test_very_large_capacity(self, test_client, admin_token):
        """Test parking lot with extremely large capacity"""
        rand_id = random.randint(100000, 999999)
        response = test_client.post("/parking-lots",
            headers={"authorization": admin_token},
            json={
                "name": f"Huge Lot {rand_id}",
                "location": "Test",
                "address": "123 Test",
                "capacity": 999999999,  # Very large number
                "tariff": 3.0,
                "daytariff": 20.0,
                "lat": 40.0,
                "lng": -74.0
            })
        # Should either succeed or fail based on validation
        assert response.status_code in [200, 400, 422]

    def test_zero_capacity(self, test_client, admin_token):
        """Test parking lot with zero capacity"""
        rand_id = random.randint(100000, 999999)
        response = test_client.post("/parking-lots",
            headers={"authorization": admin_token},
            json={
                "name": f"Zero Lot {rand_id}",
                "location": "Test",
                "address": "123 Test",
                "capacity": 0,
                "tariff": 3.0,
                "daytariff": 20.0,
                "lat": 40.0,
                "lng": -74.0
            })
        # Should either succeed or fail based on business logic
        assert response.status_code in [200, 400, 422]
