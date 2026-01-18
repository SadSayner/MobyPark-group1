import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _http_get_json(url: str, timeout_s: float = 2.0):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, resp.headers, json.loads(body)


def _wait_until_healthy(base_url: str, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    last_err = None

    while time.time() < deadline:
        try:
            status, _headers, payload = _http_get_json(f"{base_url}/health", timeout_s=2.0)
            if status == 200 and payload.get("ok") is True:
                return
        except Exception as e:  # noqa: BLE001 - used for polling readiness
            last_err = e
            time.sleep(0.2)

    raise RuntimeError(f"API did not become healthy within {timeout_s}s. Last error: {last_err!r}")


@pytest.fixture(scope="session")
def api_base_url():
    """Starts the real API with uvicorn and yields its base URL (HTTP)."""
    try:
        import uvicorn  # noqa: F401
    except Exception:
        pytest.skip("uvicorn is required for e2e tests (pip install uvicorn)")

    port = _pick_free_port()
    base_url = f"http://127.0.0.1:{port}"

    # Ensure repo root is on PYTHONPATH so `v1.server.app:app` imports reliably.
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env = os.environ.copy()
    env["PYTHONPATH"] = repo_root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env.setdefault("MOBYPARK_SKIP_SEED", "1")
    env.setdefault("MOBYPARK_DISABLE_ELASTIC_LOGS", "1")

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

    # On Windows, `CREATE_NEW_PROCESS_GROUP` lets us send CTRL_BREAK_EVENT if needed.
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

    proc = subprocess.Popen(
        cmd,
        cwd=repo_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=creationflags,
    )

    try:
        _wait_until_healthy(base_url, timeout_s=45.0)
        yield base_url
    finally:
        if proc.poll() is None:
            try:
                if os.name == "nt":
                    proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
                else:
                    proc.terminate()
            except Exception:
                proc.terminate()

        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

        # If startup failed, expose logs to help debug.
        if proc.returncode not in (0, None):
            try:
                output = (proc.stdout.read() if proc.stdout else "")
            except Exception:
                output = ""
            if output:
                print("\n--- uvicorn output (e2e) ---\n" + output)
