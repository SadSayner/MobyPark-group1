import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

import pytest


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _http_json(method: str, url: str, payload=None, headers=None, timeout_s: float = 5.0):
    data = None
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url=url, method=method, data=data, headers=req_headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8")
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return resp.status, json.loads(raw) if raw else None
            return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        try:
            body = json.loads(raw) if raw else None
        except Exception:
            body = raw
        return e.code, body


def _terminate_process(proc: subprocess.Popen, timeout_s: float = 8.0) -> None:
    if proc.poll() is not None:
        return

    try:
        if os.name == "nt":
            # We start uvicorn in a new process group; CTRL_BREAK_EVENT is the most reliable soft stop.
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.send_signal(signal.SIGINT)
    except Exception:
        pass

    try:
        proc.wait(timeout=timeout_s)
        return
    except subprocess.TimeoutExpired:
        pass

    try:
        proc.terminate()
    except Exception:
        pass

    try:
        proc.wait(timeout=timeout_s)
        return
    except subprocess.TimeoutExpired:
        pass

    try:
        proc.kill()
    except Exception:
        pass


@pytest.fixture(scope="session")
def api_base_url():
    port = _get_free_port()

    with tempfile.TemporaryDirectory(prefix="mobypark-e2e-") as tmpdir:
        db_path = os.path.join(tmpdir, "MobyPark.e2e.db")

        env = os.environ.copy()
        env["MOBYPARK_DB_PATH"] = db_path
        env["MOBYPARK_SKIP_SEED"] = "1"

        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "v1.server.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ]

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        proc = subprocess.Popen(
            cmd,
            env=env,
            cwd=os.getcwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=creationflags,
        )

        base_url = f"http://127.0.0.1:{port}"

        # Poll readiness
        deadline = time.time() + 20
        last_error = None
        while time.time() < deadline:
            try:
                status, body = _http_json("GET", f"{base_url}/health", timeout_s=1.5)
                if status == 200 and isinstance(body, dict) and body.get("ok") is True:
                    yield base_url
                    break
            except Exception as e:
                last_error = e
            time.sleep(0.25)
        else:
            output = ""
            try:
                output = (proc.stdout.read() if proc.stdout else "") or ""
            except Exception:
                pass
            _terminate_process(proc)
            raise RuntimeError(f"Server failed to start; last_error={last_error}; output=\n{output}")

        _terminate_process(proc)


@pytest.mark.e2e
def test_e2e_health(api_base_url):
    status, body = _http_json("GET", f"{api_base_url}/health")
    assert status == 200
    assert body == {"ok": True}


@pytest.mark.e2e
def test_e2e_register_login_profile(api_base_url):
    username = "e2euser01"
    password = "Passw0rd!Test"  # meets 12-30 + upper/lower/digit/special

    status, body = _http_json(
        "POST",
        f"{api_base_url}/auth/register",
        payload={
            "username": username,
            "password": password,
            "name": "E2E User",
            "email": f"{username}@example.com",
            "phone": "+31612345678",
            "role": "USER",
        },
    )
    assert status == 200, body

    status, body = _http_json(
        "POST",
        f"{api_base_url}/auth/login",
        payload={"username": username, "password": password},
    )
    assert status == 200, body
    token = body.get("session_token")
    assert token

    status, body = _http_json(
        "GET",
        f"{api_base_url}/auth/profile",
        headers={"Authorization": token},
    )
    assert status == 200, body
    assert body["username"] == username


@pytest.mark.e2e
def test_e2e_admin_creates_parking_lot_and_user_session_flow(api_base_url):
    admin_username = "e2eadmin1"
    admin_password = "AdminPassw0rd!"  # valid

    # Register + login admin
    status, body = _http_json(
        "POST",
        f"{api_base_url}/auth/register",
        payload={
            "username": admin_username,
            "password": admin_password,
            "name": "E2E Admin",
            "email": f"{admin_username}@example.com",
            "phone": "+31611111111",
            "role": "ADMIN",
        },
    )
    assert status == 200, body

    status, body = _http_json(
        "POST",
        f"{api_base_url}/auth/login",
        payload={"username": admin_username, "password": admin_password},
    )
    assert status == 200, body
    admin_token = body.get("session_token")
    assert admin_token

    # Create parking lot as admin
    status, body = _http_json(
        "POST",
        f"{api_base_url}/parking-lots",
        headers={"Authorization": admin_token},
        payload={
            "name": "E2E Lot",
            "location": "E2E City",
            "address": "E2E Street 1",
            "capacity": 10,
            "reserved": 0,
            "tariff": 2.5,
            "daytariff": 15,
            "lat": 52.0,
            "lng": 5.0,
        },
    )
    assert status == 200, body
    lot_id = body.get("id")
    assert lot_id

    # Register + login normal user
    user_username = "e2euser02"
    user_password = "UserPassw0rd!X"  # valid

    status, body = _http_json(
        "POST",
        f"{api_base_url}/auth/register",
        payload={
            "username": user_username,
            "password": user_password,
            "name": "E2E User 2",
            "email": f"{user_username}@example.com",
            "phone": "+31622222222",
            "role": "USER",
        },
    )
    assert status == 200, body

    status, body = _http_json(
        "POST",
        f"{api_base_url}/auth/login",
        payload={"username": user_username, "password": user_password},
    )
    assert status == 200, body
    user_token = body.get("session_token")
    assert user_token

    license_plate = "E2E-123"

    # Start a session
    status, body = _http_json(
        "POST",
        f"{api_base_url}/parking-lots/{lot_id}/sessions/start",
        headers={"Authorization": user_token},
        payload={"licenseplate": license_plate},
    )
    assert status == 200, body
    session_id = body.get("id")
    assert session_id

    # Stop the session
    status, body = _http_json(
        "POST",
        f"{api_base_url}/parking-lots/{lot_id}/sessions/stop",
        headers={"Authorization": user_token},
        payload={"licenseplate": license_plate},
    )
    assert status == 200, body
    assert "duration_minutes" in body
