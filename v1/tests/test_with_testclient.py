"""
FastAPI TestClient Testing Script
Tests API endpoints using FastAPI's built-in TestClient
No need to run the server separately!
"""
from fastapi.testclient import TestClient
import sys
import json

# Import the FastAPI app
from server.app import app

# Create test client
client = TestClient(app)

def print_response(title, response):
    """Pretty print response"""
    print(f"\n{'='*70}")
    print(f">>> {title}")
    print(f"{'='*70}")
    print(f"Status: {response.status_code} {response.reason_phrase}")
    try:
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response: {response.text}")

def main():
    print("MobyPark API Testing with TestClient")
    print("="*70)
    print("No need to run the server separately!")
    print("="*70)

    # Test 1: Register a user
    print("\n1  Testing: POST /register")
    response = client.post("/register", json={
        "username": "testuser",
        "password": "testpass123",
        "name": "Test User",
        "role": "USER"
    })
    print_response("Register User", response)

    if response.status_code != 200:
        print("\n  Registration failed (user might already exist). Continuing with login...")

    # Test 2: Login
    print("\n2  Testing: POST /login")
    response = client.post("/login", json={
        "username": "testuser",
        "password": "testpass123"
    })
    print_response("Login", response)

    if response.status_code != 200:
        print(" Login failed. Cannot continue with authenticated tests.")
        return

    # Get session token
    session_token = response.json()["session_token"]
    headers = {"Authorization": session_token}
    print(f"\n Session token obtained: {session_token[:30]}...")

    # Test 3: Get profile
    print("\n3  Testing: GET /profile")
    response = client.get("/profile", headers=headers)
    print_response("Get Profile", response)

    # Test 4: Update profile
    print("\n4  Testing: PUT /profile")
    response = client.put("/profile",
        headers=headers,
        json={
            "email": "testuser@example.com",
            "phone": "+1234567890"
        })
    print_response("Update Profile", response)

    # Test 5: Get updated profile
    print("\n5  Testing: GET /profile (after update)")
    response = client.get("/profile", headers=headers)
    print_response("Get Updated Profile", response)

    # Test 6: Create a vehicle
    print("\n6  Testing: POST /vehicles")
    response = client.post("/vehicles",
        headers=headers,
        json={
            "name": "Test Car",
            "license_plate": "TEST-123"
        })
    print_response("Create Vehicle", response)

    if response.status_code != 200:
        print("  Vehicle creation failed (might already exist)")

    # Test 7: List vehicles
    print("\n7  Testing: GET /vehicles")
    response = client.get("/vehicles", headers=headers)
    print_response("List My Vehicles", response)

    # Test 8: Update vehicle
    print("\n8  Testing: PUT /vehicles/TEST-123")
    response = client.put("/vehicles/TEST-123",
        headers=headers,
        json={
            "name": "Updated Test Car",
            "license_plate": "TEST-123"
        })
    print_response("Update Vehicle", response)

    # Test 9: List parking lots
    print("\n9  Testing: GET /parking-lots")
    response = client.get("/parking-lots")
    print_response("List Parking Lots", response)

    parking_lots = response.json()
    if not parking_lots:
        print("\n  No parking lots found. Creating one for testing...")

        # Test 10: Register admin user for creating parking lot
        print("\n Testing: Register Admin User")
        admin_response = client.post("/register", json={
            "username": "admin",
            "password": "adminpass",
            "name": "Admin User",
            "role": "ADMIN"
        })
        print_response("Register Admin", admin_response)

        # Login as admin
        print("\n11  Testing: Login as Admin")
        admin_login = client.post("/login", json={
            "username": "admin",
            "password": "adminpass"
        })
        print_response("Admin Login", admin_login)

        if admin_login.status_code == 200:
            admin_token = admin_login.json()["session_token"]
            admin_headers = {"Authorization": admin_token}

            # Create parking lot
            print("\n12  Testing: POST /parking-lots (Admin)")
            parking_lot_response = client.post("/parking-lots",
                headers=admin_headers,
                json={
                    "name": "Test Parking Lot",
                    "location": "Test Location",
                    "address": "123 Test Street",
                    "capacity": 100,
                    "reserved": 0,
                    "tariff": 2.5,
                    "daytariff": 20.0,
                    "lat": 40.7128,
                    "lng": -74.0060
                })
            print_response("Create Parking Lot", parking_lot_response)

            if parking_lot_response.status_code == 200:
                parking_lot_id = parking_lot_response.json()["id"]
                print(f"\n Created parking lot with ID: {parking_lot_id}")
            else:
                print("\n  Could not create parking lot")
                parking_lot_id = None
        else:
            parking_lot_id = None
    else:
        parking_lot_id = parking_lots[0]["id"]
        print(f"\n Using existing parking lot ID: {parking_lot_id}")

    # Test parking sessions
    if parking_lot_id:
        # Test 13: Start parking session
        print(f"\n13  Testing: POST /parking-lots/{parking_lot_id}/sessions/start")
        response = client.post(f"/parking-lots/{parking_lot_id}/sessions/start",
            headers=headers,
            json={"licenseplate": "TEST-123"})
        print_response("Start Parking Session", response)

        if response.status_code == 200:
            session_id = response.json()["id"]
            print(f"\n Started session with ID: {session_id}")

            # Test 14: List sessions for parking lot
            print(f"\n14  Testing: GET /parking-lots/{parking_lot_id}/sessions")
            response = client.get(f"/parking-lots/{parking_lot_id}/sessions", headers=headers)
            print_response("List Sessions", response)

            # Test 15: Get specific session
            print(f"\n15  Testing: GET /parking-lots/{parking_lot_id}/sessions/{session_id}")
            response = client.get(f"/parking-lots/{parking_lot_id}/sessions/{session_id}", headers=headers)
            print_response("Get Session Details", response)

            # Test 16: Stop parking session
            print(f"\n16  Testing: POST /parking-lots/{parking_lot_id}/sessions/stop")
            response = client.post(f"/parking-lots/{parking_lot_id}/sessions/stop",
                headers=headers,
                json={"licenseplate": "TEST-123"})
            print_response("Stop Parking Session", response)

            # Test 17: Get billing
            print("\n17  Testing: GET /billing")
            response = client.get("/billing", headers=headers)
            print_response("Get Billing Information", response)

            # Test 18: Create payment
            print("\n18  Testing: POST /payments")
            response = client.post("/payments",
                headers=headers,
                json={
                    "amount": 10.50,
                    "parkingsession_id": str(session_id)
                })
            print_response("Create Payment", response)

            if response.status_code == 200:
                transaction_id = response.json()["payment"]["transaction"]
                validation_hash = response.json()["payment"]["hash"]
                print(f"\n Payment created with transaction ID: {transaction_id}")

                # Test 19: Complete payment
                print("\n19  Testing: PUT /payments/{transaction_id}")
                response = client.put(f"/payments/{transaction_id}",
                    headers=headers,
                    json={
                        "amount": 10.50,
                        "validation": validation_hash,
                        "t_data": {
                            "t_method": "credit_card",
                            "t_issuer": "Visa",
                            "t_bank": "Test Bank"
                        }
                    })
                print_response("Complete Payment", response)

            # Test 20: List payments
            print("\n20  Testing: GET /payments")
            response = client.get("/payments", headers=headers)
            print_response("List My Payments", response)

        else:
            print("\n  Could not start parking session")

    # Test 21: Create reservation
    print("\n21  Testing: POST /reservations")
    response = client.post("/reservations",
        headers=headers,
        json={
            "licenseplate": "TEST-123",
            "startdate": "10-12-2025 09:00:00",
            "enddate": "10-12-2025 18:00:00",
            "parkinglot": str(parking_lot_id) if parking_lot_id else "1"
        })
    print_response("Create Reservation", response)

    if response.status_code == 200:
        reservation_id = response.json()["reservation"]["id"]
        print(f"\n Created reservation with ID: {reservation_id}")

        # Test 22: Get reservation
        print(f"\n22  Testing: GET /reservations/{reservation_id}")
        response = client.get(f"/reservations/{reservation_id}", headers=headers)
        print_response("Get Reservation Details", response)

        # Test 23: Update reservation
        print(f"\n23  Testing: PUT /reservations/{reservation_id}")
        response = client.put(f"/reservations/{reservation_id}",
            headers=headers,
            json={
                "licenseplate": "TEST-123",
                "startdate": "11-12-2025 10:00:00",
                "enddate": "11-12-2025 19:00:00",
                "parkinglot": str(parking_lot_id) if parking_lot_id else "1"
            })
        print_response("Update Reservation", response)

        # Test 24: Delete reservation
        print(f"\n24  Testing: DELETE /reservations/{reservation_id}")
        response = client.delete(f"/reservations/{reservation_id}", headers=headers)
        print_response("Delete Reservation", response)

    # Test 25: Delete vehicle
    print("\n25  Testing: DELETE /vehicles/TEST-123")
    response = client.delete("/vehicles/TEST-123", headers=headers)
    print_response("Delete Vehicle", response)

    # Test 26: Logout
    print("\n26  Testing: GET /logout")
    response = client.get("/logout", headers=headers)
    print_response("Logout", response)

    # Test 27: Try accessing profile after logout (should fail)
    print("\n27  Testing: GET /profile (after logout - should fail)")
    response = client.get("/profile", headers=headers)
    print_response("Access Profile After Logout", response)

    # Summary
    print("\n" + "="*70)
    print(" All tests completed!")
    print("="*70)
    print("\n Summary:")
    print("- Tested authentication (register, login, logout)")
    print("- Tested profile management")
    print("- Tested vehicle CRUD operations")
    print("- Tested parking lot listing")
    print("- Tested parking sessions (start/stop)")
    print("- Tested payments and billing")
    print("- Tested reservations")
    print("\n Tip: Check the responses above for any errors")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n Error running tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
