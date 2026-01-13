import sys
import os
import pkgutil
import importlib
import traceback
from fastapi import FastAPI


# ensure project root is on cwd so "v1" package imports resolve when running this file
ROOT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", ".."))
try:
    os.chdir(ROOT)
except Exception:
    pass

# ensure project root is on sys.path so "import v1..." works when running this file directly
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from v1.server.logging_config import log_event

# create FastAPI app and tracking lists so routers can be registered and status reported
app = FastAPI()
loaded = []
failed = []

log_event(level="INFO", event="server_startup_initiated")

# auto-include any module in v1.server.routers that exposes "router"
try:
    routers_pkg = importlib.import_module("v1.server.routers")
    for finder, name, ispkg in pkgutil.iter_modules(routers_pkg.__path__):
        if name in ("server", "__pycache__"):
            continue
        try:
            mod = importlib.import_module(f"v1.server.routers.{name}")
            router = getattr(mod, "router", None)
            if router is not None:
                app.include_router(router)
                loaded.append(name)
                log_event(level="INFO", event="router_loaded",
                          router_name=name)
            else:
                reason = "no router attribute"
                failed.append((name, reason))
                log_event(level="ERROR", event="router_load_failed",
                          router_name=name, reason=reason)
        except Exception as e:
            failed.append((name, str(e)))
            log_event(level="ERROR", event="router_load_failed",
                      router_name=name, error=str(e))
            traceback.print_exc()
except Exception as e:
    # package import failed entirely
    log_event(level="ERROR", event="router_package_import_failed", error=str(e))
    failed.append(("v1.server.routers", str(e)))
    traceback.print_exc()


@app.get("/")
def root():
    return {"status": "ok", "service": "MobyPark", "routers_loaded": loaded, "routers_failed": failed}


if __name__ == "__main__":
    # try to run with uvicorn if available, otherwise fallback to a simple WSGI dev server
    try:
        import uvicorn
        log_event(level="INFO", event="uvicorn_start_attempt",
                  host="127.0.0.1", port=8000)
        print("Starting uvicorn ASGI server (development)...")
        uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
    except Exception as e:
        log_event(level="ERROR", event="uvicorn_failed", error=str(e))
        print("uvicorn not available or failed — falling back to simple WSGI server (development only).")
        try:
            # import asgiref.wsgi dynamically to avoid static import resolution errors when not installed
            asgiref_wsgi = importlib.import_module("asgiref.wsgi")
            AsgiToWsgi = getattr(asgiref_wsgi, "AsgiToWsgi")
            from wsgiref.simple_server import make_server
            wsgi_app = AsgiToWsgi(app)
            with make_server("127.0.0.1", 8000, wsgi_app) as httpd:
                log_event(level="INFO", event="wsgi_fallback_start",
                          host="127.0.0.1", port=8000)
                print(
                    "Serving on http://127.0.0.1:8000 (WSGI fallback). Ctrl+C to stop.")
                httpd.serve_forever()
        except ModuleNotFoundError as mod_e:
            print(
                "asgiref is not installed; install it with 'pip install asgiref' to enable WSGI fallback.")
            log_event(level="WARNING",
                      event="asgiref not installed", error=mod_e)
        except Exception as fallback_e:
            print("Failed to start fallback server:", fallback_e)
            log_event(level="ERROR", event="all_server_options_failed",
                      error=str(fallback_e))
