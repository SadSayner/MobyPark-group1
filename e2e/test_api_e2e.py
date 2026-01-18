import json
import urllib.request


def _http_get(url: str, timeout_s: float = 5.0):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        headers = {k.lower(): v for k, v in dict(resp.headers).items()}
        return resp.status, headers, resp.read()


def test_health_endpoint(api_base_url: str):
    status, _headers, body = _http_get(f"{api_base_url}/health")
    assert status == 200

    payload = json.loads(body.decode("utf-8"))
    assert payload == {"ok": True}


def test_openapi_available(api_base_url: str):
    status, headers, body = _http_get(f"{api_base_url}/openapi.json")
    assert status == 200
    assert "application/json" in headers.get("content-type", "")

    payload = json.loads(body.decode("utf-8"))
    assert payload.get("openapi")
    assert payload.get("info", {}).get("title") == "MobyPark API"


def test_root_responds(api_base_url: str):
    status, headers, body = _http_get(f"{api_base_url}/")
    assert status == 200

    # Root may return HTML (static index) or JSON fallback.
    content_type = headers.get("content-type", "")
    assert ("text/html" in content_type) or ("application/json" in content_type)
    assert len(body) > 0
