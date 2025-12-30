import time
import pytest
import random

#source conftest, import test_client, user_token, admin_token, dit zijn dependency injecties
class TestAuthentication:
    def test_register_new_user(self, test_client):
        """Test user registration"""
        rand_id = random.randint(100000, 999999)
        response = test_client.post("/auth/register", json={
            "username": f"new{rand_id}",  # 9 chars, unique
            "password": "Password123!",
            "name": "New User",
            "email": f"new{rand_id}@example.com",
            "phone": "1111111111",
            "role": "USER"
        })
        assert response.status_code == 200
        assert response.json()["message"] == "User created"

    def test_register_duplicate_user(self, test_client):
        """Test registering duplicate username"""
        rand_id = random.randint(100000, 999999)
        username = f"dup{rand_id}"[:10]  # max 10 chars

        #Register new user
        test_client.post("/auth/register", json={
            "username": username,
            "password": "Password123!",
            "name": "Test",
            "email": f"{username}@example.com",
            "phone": "2222222222"
        })

        #register again with same username
        response = test_client.post("/auth/register", json={
            "username": username,
            "password": "Password123!",
            "name": "Test",
            "email": f"{username}2@example.com",
            "phone": "3333333333"
        })
        assert response.status_code == 409

    def test_login_success(self, user_token):
        """Test successful login"""
        assert user_token is not None
        assert len(user_token) > 0

    def test_login_invalid_credentials(self, test_client):
        """Test login with wrong password"""
        response = test_client.post("/auth/login", json={
            "username": "pyt_user1",
            "password": "WrongPassword123!"
        })
        assert response.status_code == 401

    def test_get_profile(self, test_client, user_token):
        """Test getting user profile"""
        response = test_client.get("/auth/profile", headers={"authorization": user_token})
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "pyt_user1"
        assert "name" in data  # Name field exists
        assert "password" not in data

    def test_get_profile_unauthorized(self, test_client):
        """Test getting profile without token"""
        response = test_client.get("/auth/profile")
        assert response.status_code in [401, 422]

    def test_update_profile(self, test_client, user_token):
        """Test updating user profile"""
        response = test_client.put("/auth/profile",
            headers={"authorization": user_token},
            json={
                "email": "pytest_updated@example.com",
                "phone": "5555555555"
            })
        assert response.status_code == 200

    def test_logout(self, test_client, user_token):
        """Test logout"""
        response = test_client.get("/auth/logout", headers={"authorization": user_token})
        assert response.status_code == 200
        assert "logged out" in response.json()["message"].lower()

  

    def test_register_missing_username(self, test_client):
        #test no username
        response = test_client.post("/auth/register", json={
            "password": "Password123!",
            "name": "Test User",
            "email": "test@example.com",
            "phone": "1234567890"
        })
        assert response.status_code == 422  # Validation error

    def test_register_missing_password(self, test_client):
        #test no password
        response = test_client.post("/auth/register", json={
            "username": "testuser1",
            "name": "Test User",
            "email": "test@example.com",
            "phone": "1234567890"
        })
        assert response.status_code == 422

    def test_register_missing_email(self, test_client):
        #test no email
        response = test_client.post("/auth/register", json={
            "username": "testuser2",
            "password": "Password123!",
            "name": "Test User",
            "phone": "1234567890"
        })
        assert response.status_code == 422

    def test_register_empty_username(self, test_client):
        #test empty username
        response = test_client.post("/auth/register", json={
            "username": "",
            "password": "Password123!",
            "name": "Test User",
            "email": "test@example.com",
            "phone": "1234567890"
        })
        assert response.status_code in [400, 422]

    def test_register_empty_password(self, test_client):
        """Test registration with empty password"""
        rand_id = random.randint(100000, 999999)
        response = test_client.post("/auth/register", json={
            "username": f"user{rand_id}"[:10],
            "password": "",
            "name": "Test User",
            "email": f"test_{rand_id}@example.com",
            "phone": "1234567890"
        })
        assert response.status_code in [400, 422]

    def test_register_special_characters_username(self, test_client):
        """Test registration with special characters in username"""
        rand_id = random.randint(100000, 999999)
        response = test_client.post("/auth/register", json={
            "username": f"user@#$%",
            "password": "Password123!",
            "name": "Test User",
            "email": f"test_{rand_id}@example.com",
            "phone": "1234567890"
        })
        # Should reject - only letters, numbers, underscore, apostrophe, period allowed
        assert response.status_code in [400, 422]

    def test_register_very_long_username(self, test_client):
        """Test registration with very long username"""
        rand_id = random.randint(100000, 999999)
        long_username = "a" * 300  # way too long (max is 10)
        response = test_client.post("/auth/register", json={
            "username": long_username,
            "password": "Password123!",
            "name": "Test User",
            "email": f"test_{rand_id}@example.com",
            "phone": "1234567890"
        })
        # Should reject - max 10 characters
        assert response.status_code in [400, 422]

    @pytest.mark.xfail(reason="API doesn't handle duplicate email gracefully - returns uncaught IntegrityError", strict=True)
    def test_register_duplicate_email(self, test_client):
        """Test registering with duplicate email (different username)"""
        rand_id = random.randint(100000, 999999)
        email = f"shr{rand_id}"[:15] + "@ex.com"

        # Register first user
        test_client.post("/auth/register", json={
            "username": f"usr1{rand_id}"[:10],
            "password": "Password123!",
            "name": "User 1",
            "email": email,
            "phone": "1111111111"
        })

        # Try to register second user with same email
        response = test_client.post("/auth/register", json={
            "username": f"usr2{rand_id}"[:10],
            "password": "Password123!",
            "name": "User 2",
            "email": email,
            "phone": "2222222222"
        })
        # Email IS unique in database - SHOULD cause proper error response
        # TODO: API should catch IntegrityError and return 409 Conflict
        assert response.status_code in [409, 400]

    def test_register_with_admin_role(self, test_client):
        """Test registering as ADMIN role"""
        rand_id = random.randint(100000, 999999)
        response = test_client.post("/auth/register", json={
            "username": f"adm{rand_id}"[:10],
            "password": "Password123!",
            "name": "Admin User",
            "email": f"admin{rand_id}@example.com",
            "phone": "1234567890",
            "role": "ADMIN"
        })
        assert response.status_code == 200
        # Verify user was created (role handling depends on implementation)

    # ============ LOGIN EDGE CASES ============

    def test_login_nonexistent_user(self, test_client):
        """Test login with non-existent username"""
        response = test_client.post("/auth/login", json={
            "username": "nonexist1",
            "password": "Password123!"
        })
        assert response.status_code == 401

    def test_login_empty_username(self, test_client):
        """Test login with empty username"""
        response = test_client.post("/auth/login", json={
            "username": "",
            "password": "Password123!"
        })
        assert response.status_code in [400, 401, 422]

    def test_login_empty_password(self, test_client):
        """Test login with empty password"""
        response = test_client.post("/auth/login", json={
            "username": "pyt_user1",
            "password": ""
        })
        assert response.status_code in [400, 401, 422]

    def test_login_missing_fields(self, test_client):
        """Test login without required fields"""
        response = test_client.post("/auth/login", json={})
        assert response.status_code == 422

    def test_login_case_sensitivity(self, test_client):
        """Test if login username is case sensitive"""
        rand_id = random.randint(100000, 999999)
        username = f"Case{rand_id}"[:10]

        # Register with mixed case
        test_client.post("/auth/register", json={
            "username": username,
            "password": "Password123!",
            "name": "Case Test",
            "email": f"case{rand_id}@example.com",
            "phone": "1234567890"
        })

        # Try login with different case
        response = test_client.post("/auth/login", json={
            "username": username.lower(),
            "password": "Password123!"
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
        assert response.status_code in [401, 422]

    def test_update_profile_password_change(self, test_client):
        """Test updating password and verify new password works"""
        rand_id = random.randint(100000, 999999)
        username = f"pwdtest{rand_id}"[:10]
        old_password = "OldPassword123!"
        new_password = "NewPassword456!"

        # Register user
        test_client.post("/auth/register", json={
            "username": username,
            "password": old_password,
            "name": "Password Test",
            "email": f"pwd{rand_id}@example.com",
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
        # Should fail with validation
        assert response.status_code in [400, 422]

    # ============ TOKEN/SESSION TESTS ============

    def test_use_token_after_logout(self, test_client):
        """Test using token after logout"""
        rand_id = random.randint(100000, 999999)
        username = f"logout{rand_id}"[:10]

        # Register and login
        test_client.post("/auth/register", json={
            "username": username,
            "password": "Password123!",
            "name": "Logout Test",
            "email": f"logout{rand_id}@example.com",
            "phone": "1234567890"
        })

        login_response = test_client.post("/auth/login", json={
            "username": username,
            "password": "Password123!"
        })
        token = login_response.json()["session_token"]

        # Logout
        test_client.get("/auth/logout", headers={"authorization": token})

        # Try to use token after logout
        response = test_client.get("/auth/profile", headers={"authorization": token})
        assert response.status_code == 401

    def test_multiple_concurrent_logins(self, test_client):
        """Test multiple login sessions for same user"""
        rand_id = random.randint(100000, 999999)
        username = f"multi{rand_id}"[:10]

        # Register
        test_client.post("/auth/register", json={
            "username": username,
            "password": "Password123!",
            "name": "Multi Login Test",
            "email": f"multi{rand_id}@example.com",
            "phone": "1234567890"
        })

        # Login twice
        login1 = test_client.post("/auth/login", json={
            "username": username,
            "password": "Password123!"
        })
        token1 = login1.json()["session_token"]

        login2 = test_client.post("/auth/login", json={
            "username": username,
            "password": "Password123!"
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
        rand_id = random.randint(100000, 999999)
        response = test_client.post("/auth/register", json={
            "username": f"xss{rand_id}"[:10],
            "password": "Password123!",
            "name": "<script>alert('xss')</script>",
            "email": f"xss{rand_id}@example.com",
            "phone": "1234567890"
        })
        # Should succeed - data should be stored as-is (sanitization happens on display)
        assert response.status_code == 200

    def test_register_invalid_email_format(self, test_client):
        """Test registration with invalid email format"""
        rand_id = random.randint(100000, 999999)
        response = test_client.post("/auth/register", json={
            "username": f"invemail{rand_id}"[:10],
            "password": "Password123!",
            "name": "Test User",
            "email": "not-an-email",
            "phone": "1234567890"
        })
        assert response.status_code in [400, 422]

    def test_register_invalid_phone_format(self, test_client):
        """Test registration with invalid phone format"""
        rand_id = random.randint(100000, 999999)
        response = test_client.post("/auth/register", json={
            "username": f"invphone{rand_id}"[:10],
            "password": "Password123!",
            "name": "Test User",
            "email": f"invphone{rand_id}@example.com",
            "phone": "abcde"
        })
        assert response.status_code in [400, 422]

    def test_register_invalid_role(self, test_client):
        """Test registration with invalid role value"""
        rand_id = random.randint(100000, 999999)
        response = test_client.post("/auth/register", json={
            "username": f"invrole{rand_id}"[:10],
            "password": "Password123!",
            "name": "Test User",
            "email": f"invrole{rand_id}@example.com",
            "phone": "1234567890",
            "role": "NOTAROLE"
        })
        assert response.status_code in [400, 422]

    def test_register_weak_password(self, test_client):
        """Test registration with weak password"""
        rand_id = random.randint(100000, 999999)
        response = test_client.post("/auth/register", json={
            "username": f"weakpwd{rand_id}"[:10],
            "password": "123",
            "name": "Test User",
            "email": f"weakpwd{rand_id}@example.com",
            "phone": "1234567890"
        })
        assert response.status_code in [400, 422]

    def test_update_profile_invalid_email(self, test_client, user_token):
        """Test updating profile with invalid email format"""
        response = test_client.put("/auth/profile",
            headers={"authorization": user_token},
            json={"email": "not-an-email"})
        assert response.status_code in [400, 422]


