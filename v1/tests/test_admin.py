import pytest


class TestAdminDashboard:
    """Test admin dashboard endpoints"""

    def test_dashboard_access_as_admin(self, test_client, admin_token):
        """Test admin can access dashboard"""
        response = test_client.get("/admin/dashboard", headers={"authorization": admin_token})
        assert response.status_code == 200
        data = response.json()

        # Check all required sections are present
        assert "users" in data
        assert "parking_lots" in data
        assert "sessions" in data
        assert "vehicles" in data
        assert "payments" in data
        assert "recent_sessions" in data
        assert "recent_payments" in data

        # Check user statistics
        assert "total" in data["users"]
        assert "admins" in data["users"]
        assert "regular_users" in data["users"]
        assert data["users"]["total"] >= 0

        # Check parking lot statistics
        assert "total" in data["parking_lots"]
        assert "total_capacity" in data["parking_lots"]
        assert "occupancy_rate" in data["parking_lots"]

        # Check payment statistics
        assert "total_revenue" in data["payments"]
        assert "net_revenue" in data["payments"]

    def test_dashboard_access_denied_for_regular_user(self, test_client, user_token):
        """Test regular user cannot access dashboard"""
        response = test_client.get("/admin/dashboard", headers={"authorization": user_token})
        assert response.status_code == 403
        assert "denied" in response.json()["detail"].lower()

    def test_dashboard_access_denied_without_token(self, test_client):
        """Test dashboard requires authentication"""
        response = test_client.get("/admin/dashboard")
        assert response.status_code in [401, 422]

    def test_list_all_users_as_admin(self, test_client, admin_token):
        """Test admin can list all users"""
        response = test_client.get("/admin/users", headers={"authorization": admin_token})
        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list)
        if len(users) > 0:
            # Check user structure (should not contain password)
            assert "username" in users[0]
            assert "email" in users[0]
            assert "role" in users[0]
            assert "password" not in users[0]

    def test_list_all_users_denied_for_regular_user(self, test_client, user_token):
        """Test regular user cannot list all users"""
        response = test_client.get("/admin/users", headers={"authorization": user_token})
        assert response.status_code == 403

    def test_get_user_details_as_admin(self, test_client, admin_token):
        """Test admin can get detailed user information"""
        # First get list of users
        users_response = test_client.get("/admin/users", headers={"authorization": admin_token})
        users = users_response.json()

        if len(users) > 0:
            user_id = users[0]["id"]
            response = test_client.get(f"/admin/users/{user_id}", headers={"authorization": admin_token})
            assert response.status_code == 200
            data = response.json()

            # Check user details
            assert "username" in data
            assert "vehicles" in data
            assert "sessions" in data
            assert "payments" in data
            assert isinstance(data["vehicles"], list)
            assert isinstance(data["sessions"], list)
            assert isinstance(data["payments"], list)

    def test_get_user_details_nonexistent_user(self, test_client, admin_token):
        """Test getting details for non-existent user"""
        response = test_client.get("/admin/users/999999", headers={"authorization": admin_token})
        assert response.status_code == 404

    def test_parking_lot_statistics(self, test_client, admin_token):
        """Test admin can get parking lot statistics"""
        response = test_client.get("/admin/parking-lots/stats", headers={"authorization": admin_token})
        assert response.status_code == 200
        stats = response.json()
        assert isinstance(stats, list)

        if len(stats) > 0:
            lot_stat = stats[0]
            assert "total_sessions" in lot_stat
            assert "active_sessions" in lot_stat
            assert "total_revenue" in lot_stat
            assert "occupancy_rate" in lot_stat

    def test_parking_lot_statistics_denied_for_user(self, test_client, user_token):
        """Test regular user cannot access parking lot statistics"""
        response = test_client.get("/admin/parking-lots/stats", headers={"authorization": user_token})
        assert response.status_code == 403

    def test_get_active_sessions(self, test_client, admin_token):
        """Test admin can get all active sessions"""
        response = test_client.get("/admin/sessions/active", headers={"authorization": admin_token})
        assert response.status_code == 200
        sessions = response.json()
        assert isinstance(sessions, list)

        # All returned sessions should have stopped = NULL
        for session in sessions:
            assert session.get("stopped") is None

    def test_active_sessions_denied_for_user(self, test_client, user_token):
        """Test regular user cannot access all active sessions"""
        response = test_client.get("/admin/sessions/active", headers={"authorization": user_token})
        assert response.status_code == 403

    def test_revenue_summary(self, test_client, admin_token):
        """Test admin can get revenue summary"""
        response = test_client.get("/admin/revenue/summary", headers={"authorization": admin_token})
        assert response.status_code == 200
        data = response.json()

        assert "revenue_by_parking_lot" in data
        assert "top_paying_users" in data
        assert isinstance(data["revenue_by_parking_lot"], list)
        assert isinstance(data["top_paying_users"], list)

    def test_revenue_summary_denied_for_user(self, test_client, user_token):
        """Test regular user cannot access revenue summary"""
        response = test_client.get("/admin/revenue/summary", headers={"authorization": user_token})
        assert response.status_code == 403

    def test_system_health(self, test_client, admin_token):
        """Test admin can get system health metrics"""
        response = test_client.get("/admin/system/health", headers={"authorization": admin_token})
        assert response.status_code == 200
        data = response.json()

        # Check health metrics are present
        assert "unpaid_completed_sessions" in data
        assert "long_active_sessions" in data
        assert "pending_payments" in data
        assert "inactive_users" in data
        assert "health_status" in data

        # Health status should be either healthy or needs_attention
        assert data["health_status"] in ["healthy", "needs_attention"]

        # All metrics should be non-negative integers
        assert data["unpaid_completed_sessions"] >= 0
        assert data["long_active_sessions"] >= 0
        assert data["pending_payments"] >= 0
        assert data["inactive_users"] >= 0

    def test_system_health_denied_for_user(self, test_client, user_token):
        """Test regular user cannot access system health"""
        response = test_client.get("/admin/system/health", headers={"authorization": user_token})
        assert response.status_code == 403
