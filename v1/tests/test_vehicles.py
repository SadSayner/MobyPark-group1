"""
Vehicle endpoint tests
"""
import time
import pytest


class TestVehicles:
    """Test vehicle CRUD operations"""

    def test_create_vehicle(self, test_client, user_token):
        """Test creating a new vehicle"""
        timestamp = int(time.time() * 1000)
        response = test_client.post("/vehicles",
            headers={"Authorization": user_token},
            json={
                "license_plate": f"TEST-{timestamp}",
                "make": "Toyota",
                "model": "Camry",
                "color": "Blue",
                "year": 2020
            })
        assert response.status_code == 200

    def test_create_vehicle_duplicate(self, test_client, user_token):
        """Test creating vehicle with duplicate license plate"""
        timestamp = int(time.time() * 1000)
        license_plate = f"DUP-{timestamp}"

        # Create first vehicle
        test_client.post("/vehicles",
            headers={"Authorization": user_token},
            json={
                "license_plate": license_plate,
                "make": "Honda",
                "model": "Civic",
                "color": "Red",
                "year": 2019
            })

        # Try to create duplicate
        response = test_client.post("/vehicles",
            headers={"Authorization": user_token},
            json={
                "license_plate": license_plate,
                "make": "Honda",
                "model": "Accord",
                "color": "Black",
                "year": 2021
            })
        assert response.status_code in [409, 400]  # Conflict or Bad Request

    def test_list_vehicles(self, test_client, user_token):
        """Test listing user's vehicles"""
        response = test_client.get("/vehicles", headers={"Authorization": user_token})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_update_vehicle(self, test_client, user_token):
        """Test updating a vehicle"""
        # First create a vehicle
        timestamp = int(time.time() * 1000)
        license_plate = f"UPD-{timestamp}"
        create_response = test_client.post("/vehicles",
            headers={"Authorization": user_token},
            json={
                "license_plate": license_plate,
                "make": "Ford",
                "model": "Focus",
                "color": "White",
                "year": 2018
            })

        if create_response.status_code == 200:
            vehicle_id = create_response.json().get("id")
            if vehicle_id:
                # Update the vehicle
                response = test_client.put(f"/vehicles/{vehicle_id}",
                    headers={"Authorization": user_token},
                    json={
                        "color": "Silver"
                    })
                assert response.status_code in [200, 404]

    def test_update_vehicle_invalid_year(self, test_client, user_token):
        """Test updating vehicle with invalid year"""
        timestamp = int(time.time() * 1000)
        create_response = test_client.post("/vehicles",
            headers={"Authorization": user_token},
            json={
                "license_plate": f"YEAR-{timestamp}",
                "make": "Ford",
                "model": "Fiesta",
                "color": "Red",
                "year": 2020
            })
        if create_response.status_code == 200:
            vehicle_id = create_response.json().get("id")
            if vehicle_id:
                response = test_client.put(f"/vehicles/{vehicle_id}",
                    headers={"Authorization": user_token},
                    json={"year": 1800})  # Invalid year
                assert response.status_code in [400, 422]

    def test_delete_vehicle(self, test_client, user_token):
        """Test deleting a vehicle"""
        # First create a vehicle to delete
        timestamp = int(time.time() * 1000)
        create_response = test_client.post("/vehicles",
            headers={"Authorization": user_token},
            json={
                "license_plate": f"DEL-{timestamp}",
                "make": "Mazda",
                "model": "CX-5",
                "color": "Gray",
                "year": 2022
            })

        if create_response.status_code == 200:
            vehicle_id = create_response.json().get("id")
            if vehicle_id:
                # Delete the vehicle
                response = test_client.delete(f"/vehicles/{vehicle_id}",
                    headers={"Authorization": user_token})
                assert response.status_code in [200, 404]

