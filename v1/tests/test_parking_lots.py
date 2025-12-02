"""
Parking lot endpoint tests
"""
import time
import pytest


class TestParkingLots:
    """Test parking lot CRUD operations"""

    def test_get_parking_lot_detail(self, test_client, user_token, parking_lot_id):
        """Test getting parking lot details"""
        response = test_client.get(f"/parking-lots/{parking_lot_id}",
            headers={"Authorization": user_token})
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == parking_lot_id

    def test_create_parking_lot_unauthorized(self, test_client, user_token):
        """Test creating parking lot without admin role"""
        timestamp = int(time.time() * 1000)
        response = test_client.post("/parking-lots",
            headers={"Authorization": user_token},
            json={
                "name": f"Unauthorized Lot {timestamp}",
                "location": "Test",
                "address": "123 Test",
                "capacity": 10,
                "tariff": 1.0,
                "daytariff": 10.0,
                "lat": 40.0,
                "lng": -74.0
            })
        assert response.status_code == 403  # Forbidden

    def test_create_parking_lot_admin(self, test_client, admin_token):
        """Test creating parking lot with admin role"""
        timestamp = int(time.time() * 1000)
        response = test_client.post("/parking-lots",
            headers={"Authorization": admin_token},
            json={
                "name": f"Admin Lot {timestamp}",
                "location": "Admin Location",
                "address": "456 Admin St",
                "capacity": 100,
                "reserved": 0,
                "tariff": 3.0,
                "daytariff": 20.0,
                "lat": 41.0,
                "lng": -73.0
            })
        assert response.status_code == 200

    def test_update_parking_lot(self, test_client, admin_token, parking_lot_id):
        """Test updating parking lot"""
        response = test_client.put(f"/parking-lots/{parking_lot_id}",
            headers={"Authorization": admin_token},
            json={
                "capacity": 75,
                "tariff": 2.5
            })
        assert response.status_code in [200, 404]

    def test_list_parking_lots(self, test_client, user_token):
        """Test listing all parking lots"""
        response = test_client.get("/parking-lots",
            headers={"Authorization": user_token})
        assert response.status_code == 200
        assert isinstance(response.json(), list)
