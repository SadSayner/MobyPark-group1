from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from v1.server.routers import auth, parking_lots, reservations, vehicles, payments
from v1.server.logging_config import log_event


def init_database():
    """
    Initialize the database on startup:
    - If database doesn't exist: create tables
    - If database exists but is empty: fill with seed data
    """
    from v1.Database.database_creation import create_database
    from v1.Database.database_logic import get_connection

    db_path = os.path.join(os.path.dirname(__file__),
                           '..', 'Database', 'MobyPark.db')
    db_path = os.path.abspath(db_path)

    db_exists = os.path.exists(db_path)

    if not db_exists:
        log_event(level="INFO", event="startup", message="Database not found, creating...")
        create_database(db_path)
        log_event(level="INFO", event="startup", message="Database tables created")

    # Check if the database has records (check users table as indicator)
    conn = get_connection(db_path)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]

        if user_count == 0:
            log_event(level="INFO", event="startup", message="Database is empty, filling with seed data...")
            conn.close()

            # Import and run fill_database
            from v1.Database.database_batches import fill_database
            fill_database(max_session_files=11)
            log_event(level="INFO", event="startup", message="Database filled with seed data")
        else:
            log_event(level="INFO", event="startup", message=f"Database contains {user_count} users, skipping seed")
            conn.close()
    except Exception as e:
        log_event(level="ERROR", event="startup", message=f"Error checking database: {e}")
        conn.close()
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    app.state.es = wait_for_elasticsearch()
    try:
        init_database()
    except Exception as e:
        print("Startup warning:", e)
    yield

# API Metadata for Swagger UI
app = FastAPI(
    lifespan=lifespan,
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

def wait_for_elasticsearch(timeout=30):
    from elasticsearch import Elasticsearch
    import time

    es = Elasticsearch("http://elasticsearch:9200")
    start = time.time()

    while time.time() - start < timeout:
        try:
            if es.ping():
                print("Elasticsearch ready")
                return es
        except Exception:
            pass
        time.sleep(2)

    print("Elasticsearch not ready, continuing without it")
    return None
