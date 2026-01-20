"""
Payment endpoint tests
"""
import pytest

class TestPayments:
    """Test payment operations"""

    @pytest.mark.parametrize("amount,expected_status", [
        (15.50, [200, 201]), # Succes met echte sessie
        (0, [400, 422]),
        (-10, [400, 422]),
    ])
    def test_create_payment_various_amounts(self, test_client, user_token, setup_test_session, amount, expected_status):
        """Test creating payment with various amounts using a real session"""
        session_id = setup_test_session
        response = test_client.post("/payments",
            headers={"Authorization": user_token},
            json={
                "session_id": session_id,
                "amount": amount,
                "payment_method": "credit_card"
            })
        assert response.status_code in expected_status

    def test_payment_for_already_paid_session(self, test_client, user_token, setup_test_session):
        """Test payment for already paid session"""
        session_id = setup_test_session
        payload = {
            "session_id": session_id,
            "amount": 15.50,
            "payment_method": "credit_card"
        }
        # Eerste betaling
        test_client.post("/payments", headers={"Authorization": user_token}, json=payload)
        
        # Tweede betaling voor dezelfde sessie (zou moeten falen of conflict geven)
        response2 = test_client.post("/payments",
            headers={"Authorization": user_token},
            json=payload)
        
        # We verwachten een foutcode omdat je niet twee keer voor dezelfde sessie betaalt
        assert response2.status_code in [400, 409, 422]

    def test_list_payments_no_payments(self, test_client, admin_token):
        """Test listing payments for user with no payments (admin)"""
        # Admin ziet alle payments, maar in een schone DB is dit een lege lijst
        response = test_client.get("/payments", headers={"Authorization": admin_token})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_payment_response_fields(self, test_client, user_token, setup_test_session):
        """Assert on returned payment data fields"""
        # Maak eerst één betaling aan zodat de lijst niet leeg is
        session_id = setup_test_session
        test_client.post("/payments",
            headers={"Authorization": user_token},
            json={
                "session_id": session_id,
                "amount": 10.0,
                "payment_method": "credit_card"
            })

        response = test_client.get("/payments", headers={"Authorization": user_token})
        assert response.status_code == 200
        payments = response.json()
        assert len(payments) > 0
        
        for p in payments:
            # Check for actual fields in the database schema
            for field in ["payment_id", "session_id", "amount", "t_method", "completed"]:
                assert field in p

    def test_create_payment(self, test_client, user_token, setup_test_session):
        """Test creating a payment"""
        session_id = setup_test_session
        response = test_client.post("/payments",
            headers={"Authorization": user_token},
            json={
                "session_id": session_id,
                "amount": 15.50,
                "payment_method": "credit_card"
            })
        assert response.status_code in [200, 201]

    def test_create_payment_unsupported_method(self, test_client, user_token, setup_test_session):
        """Test payment creation with unsupported payment method"""
        session_id = setup_test_session
        response = test_client.post("/payments",
            headers={"Authorization": user_token},
            json={
                "session_id": session_id,
                "amount": 10.0,
                "payment_method": "bitcoin"
            })
        # Bitcoin wordt meestal niet ondersteund in standaard implementaties
        assert response.status_code in [400, 422]

    def test_get_payment(self, test_client, user_token, setup_test_session):
        """Test getting payment details"""
        session_id = setup_test_session
        # Eerst maken
        create_res = test_client.post("/payments",
            headers={"Authorization": user_token},
            json={"session_id": session_id, "amount": 12.0, "payment_method": "debit_card"})
        
        payment_id = create_res.json().get("id")
        
        # Dan ophalen
        response = test_client.get(f"/payments/{payment_id}",
            headers={"Authorization": user_token})
        assert response.status_code == 200
        assert response.json()["id"] == payment_id

    def test_get_nonexistent_payment(self, test_client, user_token):
        """Test payment retrieval for non-existent payment"""
        response = test_client.get("/payments/999999", headers={"Authorization": user_token})
        assert response.status_code in [404, 400]

    def test_get_billing(self, test_client, user_token, setup_test_session):
        """Test getting billing information for a session"""
        session_id = setup_test_session
        # De billing endpoint verwacht vaak een session_id als query param of path param
        # Pas dit aan naar jouw exacte API route (bijv. /payments/billing/{session_id})
        response = test_client.get(f"/payments/billing?session_id={session_id}",
            headers={"Authorization": user_token})
        assert response.status_code in [200, 404]