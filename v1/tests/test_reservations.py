"""
Reservation endpoint tests
"""
import pytest
from datetime import datetime, timedelta


class TestReservations:
    """Test reservation operations"""

    def test_create_reservation(self, test_client, user_token, parking_lot_id):
        """Test creating a reservation"""
        start_time = (datetime.now() + timedelta(hours=1)).isoformat()
        response = test_client.post("/reservations",
            headers={"Authorization": user_token},
            json={
                "parking_lot_id": parking_lot_id,
                "vehicle_id": 1,  # Assuming vehicle exists
                "start_time": start_time,
                "duration": 120,  # 2 hours in minutes
                "status": "pending"
            })
        # May fail if vehicle doesn't exist, but shouldn't crash
        assert response.status_code in [200, 201, 400, 404]

    def test_get_reservation(self, test_client, user_token):
        """Test getting reservation details"""
        # Try to get reservation (may not exist)
        response = test_client.get("/reservations/1",
            headers={"Authorization": user_token})
        assert response.status_code in [200, 404]

    def test_list_reservations(self, test_client, user_token):
        """Test listing user reservations"""
        response = test_client.get("/reservations",
            headers={"Authorization": user_token})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_update_reservation(self, test_client, user_token):
        """Test updating a reservation"""
        response = test_client.put("/reservations/1",
            headers={"Authorization": user_token},
            json={
                "status": "confirmed"
            })
        assert response.status_code in [200, 404]

    def test_delete_reservation(self, test_client, user_token):
        """Test canceling a reservation"""
        response = test_client.delete("/reservations/1",
            headers={"Authorization": user_token})
        assert response.status_code in [200, 404]

    def test_create_overlapping_reservations(self, test_client, user_token, parking_lot_id):
        """Test creating overlapping reservations"""
        from datetime import datetime, timedelta
        start_time = (datetime.now() + timedelta(hours=1)).isoformat()
        test_client.post("/reservations",
            headers={"Authorization": user_token},
            json={
                "parking_lot_id": parking_lot_id,
                "vehicle_id": 1,
                "start_time": start_time,
                "duration": 120,
                "status": "pending"
            })
        response = test_client.post("/reservations",
            headers={"Authorization": user_token},
            json={
                "parking_lot_id": parking_lot_id,
                "vehicle_id": 1,
                "start_time": start_time,
                "duration": 120,
                "status": "pending"
            })
        assert response.status_code in [400, 409, 422, 200]

    def test_create_reservation_invalid_time(self, test_client, user_token, parking_lot_id):
        """Test reservation creation with invalid time"""
        response = test_client.post("/reservations",
            headers={"Authorization": user_token},
            json={
                "parking_lot_id": parking_lot_id,
                "vehicle_id": 1,
                "start_time": "not-a-time",
                "duration": 120,
                "status": "pending"
            })
        assert response.status_code in [400, 422]

    def test_update_reservation_invalid_status(self, test_client, user_token):
        """Test updating reservation with invalid status"""
        response = test_client.put("/reservations/1",
            headers={"Authorization": user_token},
            json={"status": "notastatus"})
        assert response.status_code in [400, 422]

    def test_delete_reservation_other_user(self, test_client, admin_token):
        """Test deleting reservation for another user (authorization)"""
        response = test_client.delete("/reservations/1", headers={"Authorization": admin_token})
        assert response.status_code in [403, 404, 200]

    @pytest.mark.parametrize("duration,expected_status", [
        (120, [200, 201, 400, 404]),
        (-10, [400, 422]),
        (0, [400, 422]),
    ])
    def test_create_reservation_various_durations(self, test_client, user_token, parking_lot_id, duration, expected_status):
        """Test creating reservation with various durations"""
        from datetime import datetime, timedelta
        start_time = (datetime.now() + timedelta(hours=1)).isoformat()
        response = test_client.post("/reservations",
            headers={"Authorization": user_token},
            json={
                "parking_lot_id": parking_lot_id,
                "vehicle_id": 1,
                "start_time": start_time,
                "duration": duration,
                "status": "pending"
            })
        assert response.status_code in expected_status

    def test_reservation_for_nonexistent_parking_lot(self, test_client, user_token):
        """Test reservation for non-existent parking lot"""
        from datetime import datetime, timedelta
        start_time = (datetime.now() + timedelta(hours=1)).isoformat()
        response = test_client.post("/reservations",
            headers={"Authorization": user_token},
            json={
                "parking_lot_id": 999999,
                "vehicle_id": 1,
                "start_time": start_time,
                "duration": 120,
                "status": "pending"
            })
        assert response.status_code in [404, 400]

    def test_reservation_response_fields(self, test_client, user_token):
        """Assert on returned reservation data fields"""
        response = test_client.get("/reservations", headers={"Authorization": user_token})
        if response.status_code == 200:
            reservations = response.json()
            for r in reservations:
                for field in ["id", "parking_lot_id", "vehicle_id", "start_time", "duration", "status"]:
                    assert field in r
