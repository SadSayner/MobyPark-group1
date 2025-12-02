"""
Authentication endpoint tests
"""
import time
import pytest


class TestAuthentication:
    """Test authentication endpoints"""

    def test_register_new_user(self, test_client):
        """Test user registration"""
        timestamp = int(time.time() * 1000)  # milliseconds for uniqueness
        response = test_client.post("/register", json={
            "username": f"newuser_{timestamp}",
            "password": "password123",
            "name": "New User",
            "email": f"newuser_{timestamp}@example.com",
            "phone": "1111111111",
            "role": "USER"
        })
        assert response.status_code == 200
        assert response.json()["message"] == "User created"

    def test_register_duplicate_user(self, test_client):
        """Test registering duplicate username"""
        timestamp = int(time.time() * 1000)
        username = f"duplicate_{timestamp}"

        # Register first time
        test_client.post("/register", json={
            "username": username,
            "password": "pass123",
            "name": "Test",
            "email": f"{username}@example.com",
            "phone": "2222222222"
        })

        # Try to register again with same username
        response = test_client.post("/register", json={
            "username": username,
            "password": "pass123",
            "name": "Test",
            "email": f"{username}_2@example.com",
            "phone": "3333333333"
        })
        assert response.status_code == 409

    def test_login_success(self, user_token):
        """Test successful login"""
        assert user_token is not None
        assert len(user_token) > 0

    def test_login_invalid_credentials(self, test_client):
        """Test login with wrong password"""
        response = test_client.post("/login", json={
            "username": "pytest_user",
            "password": "wrongpassword"
        })
        assert response.status_code == 401

    def test_get_profile(self, test_client, user_token):
        """Test getting user profile"""
        response = test_client.get("/profile", headers={"Authorization": user_token})
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "pytest_user"
        assert data["name"] == "Pytest Test User"
        assert "password" not in data

    def test_get_profile_unauthorized(self, test_client):
        """Test getting profile without token"""
        response = test_client.get("/profile")
        assert response.status_code in [401, 422]

    def test_update_profile(self, test_client, user_token):
        """Test updating user profile"""
        response = test_client.put("/profile",
            headers={"Authorization": user_token},
            json={
                "email": "pytest_updated@example.com",
                "phone": "5555555555"
            })
        assert response.status_code == 200

    def test_logout(self, test_client, user_token):
        """Test logout"""
        response = test_client.get("/logout", headers={"Authorization": user_token})
        assert response.status_code == 200
        assert "logged out" in response.json()["message"].lower()
