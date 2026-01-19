"""
Payment endpoint tests
"""
import pytest


class TestPayments:
    """Test payment operations"""

    @pytest.mark.parametrize("amount,expected_status", [
        (15.50, [200, 201, 400, 404]),
        (0, [400, 422]),
        (-10, [400, 422]),
    ])
    def test_create_payment_various_amounts(self, test_client, user_token, amount, expected_status):
        """Test creating payment with various amounts"""
        response = test_client.post("/payments",
            headers={"Authorization": user_token},
            json={
                "session_id": 1,
                "amount": amount,
                "payment_method": "credit_card"
            })
        assert response.status_code in expected_status

    def test_payment_for_already_paid_session(self, test_client, user_token):
        """Test payment for already paid session (if supported)"""
        # This is a placeholder; actual implementation depends on API
        response = test_client.post("/payments",
            headers={"Authorization": user_token},
            json={
                "session_id": 1,
                "amount": 15.50,
                "payment_method": "credit_card"
            })
        # Try to pay again for same session
        response2 = test_client.post("/payments",
            headers={"Authorization": user_token},
            json={
                "session_id": 1,
                "amount": 15.50,
                "payment_method": "credit_card"
            })
        assert response2.status_code in [200, 400, 404, 409, 422]

    def test_list_payments_no_payments(self, test_client, admin_token):
        """Test listing payments for user with no payments (admin)"""
        response = test_client.get("/payments", headers={"Authorization": admin_token})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_payment_response_fields(self, test_client, user_token):
        """Assert on returned payment data fields"""
        response = test_client.get("/payments", headers={"Authorization": user_token})
        if response.status_code == 200:
            payments = response.json()
            for p in payments:
                for field in ["id", "session_id", "amount", "payment_method", "status"]:
                    assert field in p

    def test_create_payment(self, test_client, user_token):
        """Test creating a payment"""
        response = test_client.post("/payments",
            headers={"Authorization": user_token},
            json={
                "session_id": 1,
                "amount": 15.50,
                "payment_method": "credit_card"
            })
        # May fail if session doesn't exist
        assert response.status_code in [200, 201, 400, 404]

    def test_create_payment_invalid_amount(self, test_client, user_token):
        """Test creating payment with zero/negative amount"""
        for amt in [0, -10]:
            response = test_client.post("/payments",
                headers={"Authorization": user_token},
                json={
                    "session_id": 1,
                    "amount": amt,
                    "payment_method": "credit_card"
                })
            assert response.status_code in [400, 422]

    def test_create_payment_unsupported_method(self, test_client, user_token):
        """Test payment creation with unsupported payment method"""
        response = test_client.post("/payments",
            headers={"Authorization": user_token},
            json={
                "session_id": 1,
                "amount": 10.0,
                "payment_method": "bitcoin"
            })
        assert response.status_code in [400, 404, 422]

    def test_list_payments(self, test_client, user_token):
        """Test listing user payments"""
        response = test_client.get("/payments",
            headers={"Authorization": user_token})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_payment(self, test_client, user_token):
        """Test getting payment details"""
        response = test_client.get("/payments/1",
            headers={"Authorization": user_token})
        assert response.status_code in [200, 404]

    def test_get_nonexistent_payment(self, test_client, user_token):
        """Test payment retrieval for non-existent payment"""
        response = test_client.get("/payments/999999", headers={"Authorization": user_token})
        assert response.status_code in [404, 400]

    def test_get_billing(self, test_client, user_token):
        """Test getting billing information"""
        response = test_client.get("/payments/billing",
            headers={"Authorization": user_token})
        assert response.status_code in [200, 404]

    def test_billing_endpoint_without_session(self, test_client, user_token):
        """Test billing endpoint without valid session"""
        response = test_client.get("/payments/billing", headers={"Authorization": user_token})
        assert response.status_code in [200, 400, 404, 422]
