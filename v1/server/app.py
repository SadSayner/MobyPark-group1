import sys
import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from elasticsearch import Elasticsearch

# Zorg voor directe output in de logs
sys.stdout.flush()
print("=" * 50)
print("APP.PY IS BEING LOADED")
print("=" * 50)
sys.stdout.flush()

# Import routers
print("Starting imports...")
from v1.server.routers import auth, parking_lots, reservations, vehicles, payments
from v1.server.logging_config import log_event

print("All routers imported successfully")

def wait_for_elasticsearch(timeout=60):
    """Wacht tot Elasticsearch beschikbaar is voordat de app start."""
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

    print("Warning: Elasticsearch not ready, continuing without it")
    return None

def init_database():
    """
    Initialiseert de database:
    1. Maakt altijd de tabellen aan (indien ze nog niet bestaan).
    2. Vult de database alleen als deze leeg is EN de skip-vlag niet aan staat.
    """
    print("init_database() genaamd")
    from v1.Database.database_creation import create_database
    from v1.Database.database_logic import get_connection

    # Database pad bepalen
    db_path = os.path.join(os.path.dirname(__file__), '..', 'Database', 'MobyPark.db')
    db_path = os.path.abspath(db_path)
    print(f"Database path: {db_path}")

    # STAP 1: Altijd de tabellen aanmaken (voorkomt "no such table" errors in CI)
    try:
        create_database(db_path)
        print("Database schema gecontroleerd/aangemaakt.")
    except Exception as e:
        print(f"ERROR bij aanmaken schema: {e}")
        raise

    # STAP 2: Check of we data moeten invoegen
    if os.getenv("MOBYPARK_SKIP_SEED", "").strip().lower() in {"1", "true", "yes", "y", "on"}:
        print("MOBYPARK_SKIP_SEED=1 gedetecteerd. Overslaan van data vulling.")
        log_event(level="INFO", event="startup", message="MOBYPARK_SKIP_SEED=1 set, skipping seed")
        return

    # STAP 3: Alleen vullen als de database echt leeg is
    conn = get_connection(db_path)
    try:
        # Check de payments tabel als indicator voor een volle database
        cur = conn.execute("SELECT COUNT(*) FROM payments")
        payment_count = cur.fetchone()[0]
        conn.close()

        if payment_count == 0:
            print("Database is leeg, starten van database fill (dit kan even duren)...")
            log_event(level="INFO", event="startup", message="Database is empty, filling with seed data...")
            
            from v1.Database.database_batches import fill_database
            fill_database() # Voeg eventueel parameters toe zoals max_session_files=11
            
            log_event(level="INFO", event="startup", message="Database filled with seed data")
            print("Database fill complete")
        else:
            print(f"Database bevat al {payment_count} payments, overslaan van seed.")
            log_event(level="INFO", event="startup", message=f"Database contains {payment_count} payments, skipping seed")
    except Exception as e:
        print(f"ERROR in init_database vulling: {e}")
        log_event(level="ERROR", event="startup", message=f"Error checking/filling database: {e}")
        if 'conn' in locals(): conn.close()
        # We raise de error hier niet, zodat de API alsnog kan starten met een lege DB

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager voor startup en shutdown events."""
    # Startup logica
    print("Starting up...")

    # Skip Elasticsearch if disabled
    if os.getenv("MOBYPARK_DISABLE_ELASTIC_LOGS", "").strip().lower() in {"1", "true", "yes", "y", "on"}:
        print("Elasticsearch disabled via MOBYPARK_DISABLE_ELASTIC_LOGS")
        app.state.es = None
    else:
        try:
            app.state.es = wait_for_elasticsearch()
        except Exception as e:
            print(f"Elasticsearch connection failed: {e}")
            app.state.es = None

    try:
        init_database()
        print("Database initialisatie voltooid")
    except Exception as e:
        print(f"Startup database warning: {e}")
    
    print("Application startup complete")
    yield
    # Shutdown logica
    print("Shutting down...")

# FastAPI App definitie
app = FastAPI(
    lifespan=lifespan,
    title="MobyPark API",
    description="""
    **MobyPark Parking Management System API**
    
    Deze API faciliteert:
    * **Auth**: Registratie & Login
    * **Parking**: Beheer van terreinen en sessies
    * **Betalingen**: Afhandeling van parkeerkosten
    """,
    version="1.0.0"
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes koppelen
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(parking_lots.router, tags=["parking-lots"])
app.include_router(reservations.router, tags=["reservations"])
app.include_router(vehicles.router, tags=["vehicles"])
app.include_router(payments.router, tags=["payments"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])

# Static files (Frontend)
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/")
def root():
    """Serveert index.html of een welkomstbericht."""
    static_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(static_file):
        return FileResponse(static_file)
    return {"message": "API is running. Visit /docs for documentation."}

@app.get("/health")
def health():
    """Health check endpoint voor CI/CD."""
    return {"ok": True, "database": "connected"}