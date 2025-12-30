"""
General API endpoints and middleware tests
"""
import pytest

class TestGeneralAPI:
    def test_health_check(self, test_client):
        """Test /health endpoint"""
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_root_endpoint(self, test_client):
        """Test / endpoint"""
        response = test_client.get("/")
        assert response.status_code == 200
        # Should return either index.html or JSON message
        if response.headers.get("content-type", "").startswith("application/json"):
            assert "API is running" in response.json()["message"]
        else:
            assert "text/html" in response.headers.get("content-type", "")


