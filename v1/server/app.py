from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
from logging_config import log_event

from .routers import auth, parking_lots, reservations, vehicles, payments

app = FastAPI(title="Parking API")

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
    static_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(static_file):
        return FileResponse(static_file)
    return {"message": "API is running. Visit /docs for API documentation."}

@app.get("/health")
def health():
    return {"ok": True}
