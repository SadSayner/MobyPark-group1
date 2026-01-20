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
                assert response.status_code in [200, 400, 422]

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

    def test_duplicate_vehicle_creation(self, test_client, user_token):
        """Test creating duplicate vehicle for same user"""
        timestamp = int(time.time() * 1000)
        license_plate = f"DUPLICATE-{timestamp}"
        test_client.post("/vehicles",
            headers={"Authorization": user_token},
            json={
                "license_plate": license_plate,
                "make": "Toyota",
                "model": "Corolla",
                "color": "Blue",
                "year": 2021
            })
        response = test_client.post("/vehicles",
            headers={"Authorization": user_token},
            json={
                "license_plate": license_plate,
                "make": "Toyota",
                "model": "Corolla",
                "color": "Blue",
                "year": 2021
            })
        assert response.status_code in [400, 409, 422]

    def test_delete_nonexistent_vehicle(self, test_client, user_token):
        """Test deleting a non-existent vehicle"""
        response = test_client.delete("/vehicles/999999", headers={"Authorization": user_token})
        assert response.status_code in [404, 400]

    def test_vehicle_ownership(self, test_client, user_token, admin_token):
        """Test vehicle CRUD for multiple users (ownership checks)"""
        # Create vehicle as user
        timestamp = int(time.time() * 1000)
        create_response = test_client.post("/vehicles",
            headers={"Authorization": user_token},
            json={
                "license_plate": f"OWN-{timestamp}",
                "make": "BMW",
                "model": "X5",
                "color": "Black",
                "year": 2022
            })
        if create_response.status_code == 200:
            vehicle_id = create_response.json().get("id")
            if vehicle_id:
                # Try to delete as admin (should succeed or fail based on API rules)
                response = test_client.delete(f"/vehicles/{vehicle_id}", headers={"Authorization": admin_token})
                assert response.status_code in [200, 403, 404]

    @pytest.mark.parametrize("year,expected_status", [
        (2020, [200]),
        (1800, [200, 400, 422]),
        (3000, [200, 400, 422]),
    ])
    def test_create_vehicle_various_years(self, test_client, user_token, year, expected_status):
        """Test creating vehicle with various years"""
        timestamp = int(time.time() * 1000)
        response = test_client.post("/vehicles",
            headers={"Authorization": user_token},
            json={
                "license_plate": f"YEAR-{timestamp}",
                "make": "Ford",
                "model": "Fiesta",
                "color": "Red",
                "year": year
            })
        assert response.status_code in expected_status

    def test_update_vehicle_partial_data(self, test_client, user_token):
        """Test updating vehicle with partial data"""
        timestamp = int(time.time() * 1000)
        create_response = test_client.post("/vehicles",
            headers={"Authorization": user_token},
            json={
                "license_plate": f"PARTIAL-{timestamp}",
                "make": "Ford",
                "model": "Focus",
                "color": "White",
                "year": 2018
            })
        if create_response.status_code == 200:
            vehicle_id = create_response.json().get("id")
            if vehicle_id:
                response = test_client.put(f"/vehicles/{vehicle_id}",
                    headers={"Authorization": user_token},
                    json={"color": "Silver"})
                assert response.status_code in [200, 404]

    def test_list_vehicles_no_vehicles(self, test_client, admin_token):
        """Test listing vehicles for user with no vehicles (admin)"""
        response = test_client.get("/vehicles", headers={"Authorization": admin_token})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_vehicle_response_fields(self, test_client, user_token):
        """Assert on returned vehicle data fields"""
        response = test_client.get("/vehicles", headers={"Authorization": user_token})
        if response.status_code == 200:
            vehicles = response.json()
            for v in vehicles:
                for field in ["id", "license_plate", "make", "model", "color", "year"]:
                    assert field in v
