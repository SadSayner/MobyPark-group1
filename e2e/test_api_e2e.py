import json
import time
import urllib.error
import urllib.request


def _http_get(url: str, timeout_s: float = 5.0):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        headers = {k.lower(): v for k, v in dict(resp.headers).items()}
        return resp.status, headers, resp.read()


def _http_json(method: str, url: str, *, json_body=None, headers=None, timeout_s: float = 10.0):
    headers = dict(headers or {})
    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, method=method, data=data, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw_headers = {k.lower(): v for k, v in dict(resp.headers).items()}
            body = resp.read()
            payload = json.loads(body.decode("utf-8")) if body else None
            return resp.status, raw_headers, payload
    except urllib.error.HTTPError as e:
        raw_headers = {k.lower(): v for k, v in dict(e.headers).items()}
        try:
            body = e.read()
        except TimeoutError:
            body = b""
        try:
            payload = json.loads(body.decode("utf-8")) if body else None
        except Exception:
            payload = body.decode("utf-8", errors="replace") if body else None
        return int(e.code), raw_headers, payload


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


def test_auth_register_login_profile_and_vehicle_flow(api_base_url: str):
    # Username must be 8-10 chars and start with a letter/underscore.
    # Use a time-based suffix to avoid collisions across runs.
    suffix = f"{int(time.time() * 1000) % 10_000_000:07d}"
    username = f"e{suffix}"  # 8 chars total

    user = {
        "username": username,
        "password": "E2ePass1234!",  # 12 chars, has upper/lower/digit/special
        "name": "E2E User",
        "email": f"{username}@example.com",
        "phone": "1234567890",
        "role": "USER",
    }

    # Register (if a rare collision happens, retry once)
    status, _headers, payload = _http_json("POST", f"{api_base_url}/auth/register", json_body=user)
    if status == 409:
        suffix = f"{(int(time.time() * 1000) + 1) % 10_000_000:07d}"
        username = f"e{suffix}"
        user["username"] = username
        user["email"] = f"{username}@example.com"
        status, _headers, payload = _http_json("POST", f"{api_base_url}/auth/register", json_body=user)
    assert status == 200, payload

    # Login
    status, _headers, payload = _http_json(
        "POST",
        f"{api_base_url}/auth/login",
        json_body={"username": user["username"], "password": user["password"]},
    )
    assert status == 200, payload
    token = payload["session_token"]
    assert isinstance(token, str) and len(token) > 10

    # Authenticated profile
    status, _headers, payload = _http_json(
        "GET",
        f"{api_base_url}/auth/profile",
        headers={"Authorization": token},
    )
    assert status == 200, payload
    assert payload["username"] == user["username"]
    assert payload["role"] == "USER"

    # Create a vehicle
    plate = f"E2E-{suffix[-4:]}"
    status, _headers, payload = _http_json(
        "POST",
        f"{api_base_url}/vehicles",
        headers={"Authorization": token},
        json_body={
            "license_plate": plate,
            "make": "TestMake",
            "model": "TestModel",
            "color": "Black",
            "year": 2020,
        },
    )
    assert status == 200, payload
    assert payload["license_plate"] == plate

    # List own vehicles and verify it’s there
    status, _headers, payload = _http_json(
        "GET",
        f"{api_base_url}/vehicles",
        headers={"Authorization": token},
    )
    assert status == 200, payload
    assert isinstance(payload, list)
    assert any(v.get("license_plate") == plate for v in payload)

    # Logout invalidates token
    status, _headers, payload = _http_json(
        "GET",
        f"{api_base_url}/auth/logout",
        headers={"Authorization": token},
    )
    assert status == 200, payload

    status, _headers, payload = _http_json(
        "GET",
        f"{api_base_url}/auth/profile",
        headers={"Authorization": token},
    )
    assert status == 401


def test_admin_can_create_and_delete_parking_lot(api_base_url: str):
    suffix = f"{int(time.time() * 1000) % 10_000_000:07d}"
    username = f"a{suffix}"  # 8 chars total

    admin = {
        "username": username,
        "password": "AdmPass1234!",
        "name": "E2E Admin",
        "email": f"{username}@example.com",
        "phone": "1234567890",
        "role": "ADMIN",
    }

    status, _headers, payload = _http_json("POST", f"{api_base_url}/auth/register", json_body=admin)
    if status == 409:
        suffix = f"{(int(time.time() * 1000) + 1) % 10_000_000:07d}"
        username = f"a{suffix}"
        admin["username"] = username
        admin["email"] = f"{username}@example.com"
        status, _headers, payload = _http_json("POST", f"{api_base_url}/auth/register", json_body=admin)
    assert status == 200, payload

    status, _headers, payload = _http_json(
        "POST",
        f"{api_base_url}/auth/login",
        json_body={"username": admin["username"], "password": admin["password"]},
    )
    assert status == 200, payload
    token = payload["session_token"]

    # Create parking lot
    lot_payload = {
        "name": f"E2E Lot {suffix}",
        "location": "E2E City",
        "address": "1 Test Street",
        "capacity": 10,
        "reserved": 0,
        "tariff": 2.5,
        "daytariff": 15.0,
        "lat": 52.3702,
        "lng": 4.8952,
    }
    status, _headers, payload = _http_json(
        "POST",
        f"{api_base_url}/parking-lots",
        headers={"Authorization": token},
        json_body=lot_payload,
    )
    assert status == 200, payload
    lot_id = payload["id"]

    # Fetch it
    status, _headers, payload = _http_json("GET", f"{api_base_url}/parking-lots/{lot_id}")
    assert status == 200, payload
    assert payload.get("id") == lot_id
    assert payload.get("name") == lot_payload["name"]

    # Delete it
    status, _headers, payload = _http_json(
        "DELETE",
        f"{api_base_url}/parking-lots/{lot_id}",
        headers={"Authorization": token},
    )
    assert status == 200, payload

    # Verify gone
    status, _headers, payload = _http_json("GET", f"{api_base_url}/parking-lots/{lot_id}")
    assert status == 404
