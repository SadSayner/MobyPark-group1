from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
from v1.server.logging_config import log_event
import time

from .routers import auth, parking_lots, reservations, vehicles, payments

# API Metadata for Swagger UI
app = FastAPI(
    title="MobyPark API",
    description="""
    **MobyPark Parking Management System API**

    This API provides endpoints for:
    * **Authentication** - User registration, login, profile management
    * **Parking Lots** - CRUD operations for parking lots and parking sessions
    * **Vehicles** - Manage user vehicles
    * **Reservations** - Create and manage parking reservations
    * **Payments** - Handle payments and billing

    ## Authentication
    Most endpoints require authentication via session token in the `Authorization` header.

    ## Roles
    * **USER** - Regular user (can manage own data)
    * **ADMIN** - Administrator (can manage all data)
    """,
    version="1.0.0",
    contact={
        "name": "MobyPark Team",
        "email": "support@mobypark.com",
    },
    license_info={
        "name": "MIT",
    },
)


@app.middleware("http")
async def elastic_request_logger(request: Request, call_next):
    start = time.time()

    try:
        response = await call_next(request)
        return response
    finally:
        duration = round((time.time() - start) * 1000, 2)

        if getattr(response, "status_code", None) == 500:
            log_event(
                level="ERROR",
                event="http_request",
                method=request.method,
                path=request.url.path,
                status_code=getattr(response, "status_code", None),
                response_time_ms=duration,
                exc_info=True,
            )
        elif getattr(response, "status_code", None) != 200:
            log_event(
                level="ERROR",
                event="http_request",
                method=request.method,
                path=request.url.path,
                status_code=getattr(response, "status_code", None),
                response_time_ms=duration,
            )
        else:
            log_event(
                level="INFO",
                event="http_request",
                method=request.method,
                path=request.url.path,
                status_code=getattr(response, "status_code", None),
                response_time_ms=duration,
            )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# mount routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(parking_lots.router, tags=["parking-lots"])
app.include_router(reservations.router, tags=["reservations"])
app.include_router(vehicles.router, tags=["vehicles"])
app.include_router(payments.router, tags=["payments"])

# Mount static files
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")


@app.get("/")
def root():
    """Serve the simple testing interface"""
    static_file = os.path.join(os.path.dirname(
        __file__), "static", "index.html")
    if os.path.exists(static_file):
        return FileResponse(static_file)
    return {"message": "API is running. Visit /docs for API documentation."}


@app.get("/health")
def health():
    return {"ok": True}
