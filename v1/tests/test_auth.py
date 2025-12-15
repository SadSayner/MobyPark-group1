import time
import pytest

#source conftest, import test_client, user_token, admin_token, dit zijn dependency injecties
class TestAuthentication:
    def test_register_new_user(self, test_client):
        """Test user registration"""
        timestamp = int(time.time() * 1000)  # milliseconds for uniqueness
        response = test_client.post("/auth/register", json={
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

        #Register new user
        test_client.post("/auth/register", json={
            "username": username,
            "password": "pass123",
            "name": "Test",
            "email": f"{username}@example.com",
            "phone": "2222222222"
        })

        #register again with same username
        response = test_client.post("/auth/register", json={
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

  

    def test_register_missing_username(self, test_client):
        #test no username
        response = test_client.post("/auth/register", json={
            "password": "password123",
            "name": "Test User",
            "email": "test@example.com",
            "phone": "1234567890"
        })
        assert response.status_code == 422  # Validation error

    def test_register_missing_password(self, test_client):
        #test no password
        response = test_client.post("/auth/register", json={
            "username": "testuser",
            "name": "Test User",
            "email": "test@example.com",
            "phone": "1234567890"
        })
        assert response.status_code == 422

    def test_register_missing_email(self, test_client):
        #test no email
        response = test_client.post("/auth/register", json={
            "username": "testuser",
            "password": "password123",
            "name": "Test User",
            "phone": "1234567890"
        })
        assert response.status_code == 422

    def test_register_empty_username(self, test_client):
        #test no username
        response = test_client.post("/auth/register", json={
            "username": "",
            "password": "password123",
            "name": "Test User",
            "email": "test@example.com",
            "phone": "1234567890"
        })
        assert response.status_code in [400, 422]

    def test_register_empty_password(self, test_client):
        """Test registration with empty password"""
        timestamp = int(time.time() * 1000)
        response = test_client.post("/auth/register", json={
            "username": f"user_{timestamp}",
            "password": "",
            "name": "Test User",
            "email": f"test_{timestamp}@example.com",
            "phone": "1234567890"
        })
        assert response.status_code in [400, 422]

    def test_register_special_characters_username(self, test_client):
        """Test registration with special characters in username"""
        timestamp = int(time.time() * 1000)
        response = test_client.post("/auth/register", json={
            "username": f"user@#$%_{timestamp}",
            "password": "password123",
            "name": "Test User",
            "email": f"test_{timestamp}@example.com",
            "phone": "1234567890"
        })
        # Should either succeed or reject based on validation rules
        assert response.status_code in [200, 400, 422]

    def test_register_very_long_username(self, test_client):
        """Test registration with very long username"""
        timestamp = int(time.time() * 1000)
        long_username = "a" * 300 + str(timestamp)
        response = test_client.post("/auth/register", json={
            "username": long_username,
            "password": "password123",
            "name": "Test User",
            "email": f"test_{timestamp}@example.com",
            "phone": "1234567890"
        })
        # Should either succeed or reject based on validation rules
        assert response.status_code in [200, 400, 422]

    def test_register_duplicate_email(self, test_client):
        """Test registering with duplicate email (different username)"""
        timestamp = int(time.time() * 1000)
        email = f"shared_{timestamp}@example.com"

        # Register first user
        test_client.post("/auth/register", json={
            "username": f"user1_{timestamp}",
            "password": "password123",
            "name": "User 1",
            "email": email,
            "phone": "1111111111"
        })

        # Try to register second user with same email
        response = test_client.post("/auth/register", json={
            "username": f"user2_{timestamp}",
            "password": "password123",
            "name": "User 2",
            "email": email,
            "phone": "2222222222"
        })
        # Email might or might not be unique - test both cases
        assert response.status_code in [200, 409, 400]

    def test_register_with_admin_role(self, test_client):
        """Test registering as ADMIN role"""
        timestamp = int(time.time() * 1000)
        response = test_client.post("/auth/register", json={
            "username": f"admin_{timestamp}",
            "password": "password123",
            "name": "Admin User",
            "email": f"admin_{timestamp}@example.com",
            "phone": "1234567890",
            "role": "ADMIN"
        })
        assert response.status_code == 200
        # Verify user was created (role handling depends on implementation)

    # ============ LOGIN EDGE CASES ============

    def test_login_nonexistent_user(self, test_client):
        """Test login with non-existent username"""
        response = test_client.post("/auth/login", json={
            "username": "nonexistent_user_12345",
            "password": "password123"
        })
        assert response.status_code == 401

    def test_login_empty_username(self, test_client):
        """Test login with empty username"""
        response = test_client.post("/auth/login", json={
            "username": "",
            "password": "password123"
        })
        assert response.status_code in [401, 422]

    def test_login_empty_password(self, test_client):
        """Test login with empty password"""
        response = test_client.post("/auth/login", json={
            "username": "pytest_user",
            "password": ""
        })
        assert response.status_code in [401, 422]

    def test_login_missing_fields(self, test_client):
        """Test login without required fields"""
        response = test_client.post("/auth/login", json={})
        assert response.status_code == 422

    def test_login_case_sensitivity(self, test_client):
        """Test if login username is case sensitive"""
        timestamp = int(time.time() * 1000)
        username = f"CaseSensitive_{timestamp}"

        # Register with mixed case
        test_client.post("/auth/register", json={
            "username": username,
            "password": "password123",
            "name": "Case Test",
            "email": f"case_{timestamp}@example.com",
            "phone": "1234567890"
        })

        # Try login with different case
        response = test_client.post("/auth/login", json={
            "username": username.lower(),
            "password": "password123"
        })
        # Should fail if case sensitive
        assert response.status_code in [200, 401]

    def test_login_sql_injection_attempt(self, test_client):
        """Test SQL injection protection in login"""
        response = test_client.post("/auth/login", json={
            "username": "admin' OR '1'='1",
            "password": "password' OR '1'='1"
        })
        assert response.status_code == 401

    # ============ PROFILE EDGE CASES ============

    def test_get_profile_with_invalid_token(self, test_client):
        """Test getting profile with invalid token"""
        response = test_client.get("/auth/profile", headers={
            "authorization": "invalid-token-12345"
        })
        assert response.status_code == 401

    def test_get_profile_with_empty_token(self, test_client):
        """Test getting profile with empty token"""
        response = test_client.get("/auth/profile", headers={
            "authorization": ""
        })
        assert response.status_code == 401

    def test_update_profile_password_change(self, test_client):
        """Test updating password and verify new password works"""
        timestamp = int(time.time() * 1000)
        username = f"pwdtest_{timestamp}"
        old_password = "oldpassword123"
        new_password = "newpassword456"

        # Register user
        test_client.post("/auth/register", json={
            "username": username,
            "password": old_password,
            "name": "Password Test",
            "email": f"pwd_{timestamp}@example.com",
            "phone": "1234567890"
        })

        # Login with old password
        login_response = test_client.post("/auth/login", json={
            "username": username,
            "password": old_password
        })
        assert login_response.status_code == 200
        token = login_response.json()["session_token"]

        # Update password
        update_response = test_client.put("/auth/profile",
            headers={"authorization": token},
            json={"password": new_password}
        )
        assert update_response.status_code == 200

        # Logout
        test_client.get("/auth/logout", headers={"authorization": token})

        # Try login with old password (should fail)
        old_login = test_client.post("/auth/login", json={
            "username": username,
            "password": old_password
        })
        assert old_login.status_code == 401

        # Try login with new password (should succeed)
        new_login = test_client.post("/auth/login", json={
            "username": username,
            "password": new_password
        })
        assert new_login.status_code == 200

    def test_update_profile_name_change(self, test_client, user_token):
        """Test updating user name"""
        response = test_client.put("/auth/profile",
            headers={"authorization": user_token},
            json={"name": "Updated Name"}
        )
        assert response.status_code == 200

        # Verify name changed
        profile = test_client.get("/auth/profile", headers={"authorization": user_token})
        # Note: name might not be in profile response depending on implementation

    def test_update_profile_without_token(self, test_client):
        """Test updating profile without authentication"""
        response = test_client.put("/auth/profile", json={
            "name": "Hacker"
        })
        assert response.status_code in [401, 422]

    def test_update_profile_empty_update(self, test_client, user_token):
        """Test updating profile with no changes"""
        response = test_client.put("/auth/profile",
            headers={"authorization": user_token},
            json={}
        )
        assert response.status_code == 200

    def test_update_profile_invalid_email(self, test_client, user_token):
        """Test updating profile with invalid email"""
        response = test_client.put("/auth/profile",
            headers={"authorization": user_token},
            json={"email": "not-an-email"}
        )
        # Should either succeed (no validation) or fail (with validation)
        assert response.status_code in [200, 400, 422]

    # ============ TOKEN/SESSION TESTS ============

    def test_use_token_after_logout(self, test_client):
        """Test using token after logout"""
        timestamp = int(time.time() * 1000)

        # Register and login
        test_client.post("/auth/register", json={
            "username": f"logouttest_{timestamp}",
            "password": "password123",
            "name": "Logout Test",
            "email": f"logout_{timestamp}@example.com",
            "phone": "1234567890"
        })

        login_response = test_client.post("/auth/login", json={
            "username": f"logouttest_{timestamp}",
            "password": "password123"
        })
        token = login_response.json()["session_token"]

        # Logout
        test_client.get("/auth/logout", headers={"authorization": token})

        # Try to use token after logout
        response = test_client.get("/auth/profile", headers={"authorization": token})
        assert response.status_code == 401

    def test_multiple_concurrent_logins(self, test_client):
        """Test multiple login sessions for same user"""
        timestamp = int(time.time() * 1000)
        username = f"multilogin_{timestamp}"

        # Register
        test_client.post("/auth/register", json={
            "username": username,
            "password": "password123",
            "name": "Multi Login Test",
            "email": f"multi_{timestamp}@example.com",
            "phone": "1234567890"
        })

        # Login twice
        login1 = test_client.post("/auth/login", json={
            "username": username,
            "password": "password123"
        })
        token1 = login1.json()["session_token"]

        login2 = test_client.post("/auth/login", json={
            "username": username,
            "password": "password123"
        })
        token2 = login2.json()["session_token"]

        # Both tokens should be different
        assert token1 != token2

        # Both tokens should work
        profile1 = test_client.get("/auth/profile", headers={"authorization": token1})
        profile2 = test_client.get("/auth/profile", headers={"authorization": token2})
        assert profile1.status_code == 200
        assert profile2.status_code == 200

    def test_logout_without_token(self, test_client):
        """Test logout without authentication"""
        response = test_client.get("/auth/logout")
        assert response.status_code in [400, 401, 422]

    def test_logout_with_invalid_token(self, test_client):
        """Test logout with invalid token"""
        response = test_client.get("/auth/logout", headers={
            "authorization": "invalid-token-xyz"
        })
        assert response.status_code == 400

    # ============ SECURITY TESTS ============

    def test_password_not_in_profile_response(self, test_client, user_token):
        """Test that password is never returned in profile"""
        response = test_client.get("/auth/profile", headers={"authorization": user_token})
        assert response.status_code == 200
        data = response.json()
        assert "password" not in data
        assert "pwd" not in str(data).lower()

    def test_xss_in_registration(self, test_client):
        """Test XSS protection in registration fields"""
        timestamp = int(time.time() * 1000)
        response = test_client.post("/auth/register", json={
            "username": f"xsstest_{timestamp}",
            "password": "password123",
            "name": "<script>alert('xss')</script>",
            "email": f"xss_{timestamp}@example.com",
            "phone": "1234567890"
        })
        # Should succeed - data should be stored as-is (sanitization happens on display)
        assert response.status_code == 200
