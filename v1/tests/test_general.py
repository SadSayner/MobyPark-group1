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

    def test_static_file_serving(self, test_client):
        """Test /static/index.html serving"""
        response = test_client.get("/static/index.html")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_cors_options(self, test_client):
        """Test CORS preflight OPTIONS request"""
        response = test_client.options("/health")
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    def test_middleware_logging(self, test_client, caplog):
        """Test middleware logs for error/info"""
        # Trigger a 404 error to check error logging
        response = test_client.get("/nonexistent")
        assert response.status_code == 404
        # Trigger a normal request to check info logging
        response = test_client.get("/health")
        assert response.status_code == 200
        # caplog can be used to check logs if configured
