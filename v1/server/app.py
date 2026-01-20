import sys
sys.stdout.flush()
print("=" * 50)
print("APP.PY IS BEING LOADED")
print("=" * 50)
sys.stdout.flush()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

print("Starting imports...")

print("Importing auth router...")
from v1.server.routers import auth

print("Importing parking_lots router...")
from v1.server.routers import parking_lots

print("Importing reservations router...")
from v1.server.routers import reservations

print("Importing vehicles router...")
from v1.server.routers import vehicles

print("Importing payments router...")
from v1.server.routers import payments

print("All routers imported successfully")

from v1.server.logging_config import log_event

def wait_for_elasticsearch(timeout=60):
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
            print(f"Waiting for Elasticsearch... ({int(time.time() - start)}s elapsed)")
        time.sleep(2)

    raise RuntimeError(f"Elasticsearch not ready after {timeout} seconds. Cannot start application.")

def init_database():
    """
    Initialize the database on startup:
    - If database doesn't exist: create tables
    - If database exists but is empty: fill with seed data
    """
    print("init_database() called")
    from v1.Database.database_creation import create_database
    from v1.Database.database_logic import get_connection

    db_path = os.path.join(os.path.dirname(__file__),
                           '..', 'Database', 'MobyPark.db')
    db_path = os.path.abspath(db_path)
    
    print(f"Database path: {db_path}")

    db_exists = os.path.exists(db_path)
    print(f"Database exists: {db_exists}")

    if not db_exists:
        print("Creating database...")
        log_event(level="INFO", event="startup", message="Database not found, creating...")
        create_database(db_path)
        log_event(level="INFO", event="startup", message="Database tables created")
        print("Database created")

    # Check if the database has records (check users table as indicator)
    print("Connecting to database...")
    conn = get_connection(db_path)
    try:
        print("Checking payment count...")
        cur = conn.execute("SELECT COUNT(*) FROM payments")
        payment_count = cur.fetchone()[0]
        print(f"Payment count: {payment_count}")
        conn.close()

        if payment_count == 0:
            if os.getenv("MOBYPARK_SKIP_SEED", "").strip().lower() in {"1", "true", "yes", "y", "on"}:
                log_event(level="INFO", event="startup", message="MOBYPARK_SKIP_SEED=1 set, skipping seed")
            else:
                print("Starting database fill (this may take a while)...")
                log_event(level="INFO", event="startup", message="Database is empty, filling with seed data...")

                from v1.Database.database_batches import fill_database
                fill_database()
                log_event(level="INFO", event="startup", message="Database filled with seed data")
                print("Database fill complete")
        else:
            print(f"Database already has {payment_count} payments, skipping seed")
            log_event(level="INFO", event="startup", message=f"Database contains {payment_count} payments, skipping seed")
    except Exception as e:
        print(f"ERROR in init_database: {e}")
        log_event(level="ERROR", event="startup", message=f"Error checking database: {e}")
        conn.close()
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    print("Starting up...")
    app.state.es = wait_for_elasticsearch()
    print("Elasticsearch connected successfully")
    
    try:
        init_database()
        print("Database initialized")
    except Exception as e:
        print(f"Startup warning: {e}")
    
    print("Application startup complete")
    yield
    # Shutdown
    print("Shutting down...")

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
