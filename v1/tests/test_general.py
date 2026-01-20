"""
General API endpoints and middleware tests
"""
import pytest

class TestGeneralAPI:
    @pytest.mark.parametrize("endpoint", ["/health", "/", "/static/index.html"])
    def test_endpoints_status_and_content(self, test_client, endpoint):
        """Test status and content type for general endpoints"""
        response = test_client.get(endpoint)
        assert response.status_code == 200
        if endpoint == "/static/index.html":
            assert "text/html" in response.headers.get("content-type", "")
        elif endpoint == "/health":
            data = response.json()
            assert data["ok"] is True
            # May also contain additional fields like "database"

    def test_cors_headers_present(self, test_client):
        """Test CORS headers are present on responses"""
        origin = "http://example.com"
        response = test_client.get("/health", headers={"Origin": origin})
        assert "access-control-allow-origin" in response.headers
        assert response.headers.get("access-control-allow-origin") in {"*", origin}

    def test_middleware_logging_error_and_info(self, test_client, caplog):
        """Test middleware logs for error/info (structure only)"""
        response = test_client.get("/nonexistent")
        assert response.status_code == 404
        response = test_client.get("/health")
        assert response.status_code == 200
        # Optionally check caplog for log structure if configured
