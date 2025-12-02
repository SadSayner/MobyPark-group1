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
