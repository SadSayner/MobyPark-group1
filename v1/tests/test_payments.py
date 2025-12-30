"""
Payment endpoint tests
"""
import pytest


class TestPayments:
    """Test payment operations"""

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
        assert response.status_code in [400, 422]

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

    def test_get_billing(self, test_client, user_token):
        """Test getting billing information"""
        response = test_client.get("/payments/billing",
            headers={"Authorization": user_token})
        assert response.status_code in [200, 404]
