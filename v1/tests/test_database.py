"""
Database logic tests for CRUD operations
"""
import pytest
import sqlite3
from v1.Database import database_logic
from datetime import datetime

TEST_DB = "v1/Database/test_db.sqlite"

def setup_module(module):
    # Create a fresh test database before running tests
    con = sqlite3.connect(TEST_DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    # Create minimal users table
    con.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        password TEXT NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        phone TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'USER',
        created_at TEXT NOT NULL,
        birth_year INTEGER NOT NULL,
        active INTEGER NOT NULL
    );
    """)
    # Create minimal parking_lots table
    con.execute("""
    CREATE TABLE IF NOT EXISTS parking_lots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        location TEXT NOT NULL,
        address TEXT NOT NULL,
        capacity INTEGER NOT NULL,
        reserved INTEGER NOT NULL,
        tariff REAL NOT NULL,
        daytariff REAL NOT NULL,
        created_at TEXT NOT NULL,
        lat REAL NOT NULL,
        lng REAL NOT NULL
    );
    """)
    con.commit()
    con.close()

def teardown_module(module):
    import os
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

class DummyUser:
    def __init__(self, username=None, email=None):
        import uuid
        self.id = None
        self.username = username or f"user_{uuid.uuid4().hex[:8]}"
        self.password = "pass123"
        self.name = "Test User"
        self.email = email or f"{self.username}@example.com"
        self.phone = "1234567890"
        self.role = "USER"
        self.created_at = datetime.now().strftime("%Y-%m-%d")
        self.birth_year = 1990
        self.active = True

class DummyParkingLot:
    def __init__(self, name=None):
        import uuid
        self.id = None
        self.name = name or f"Lot_{uuid.uuid4().hex[:8]}"
        self.location = "Test Location"
        self.address = "Test Address"
        self.capacity = 10
        self.reserved = 0
        self.tariff = 2.5
        self.daytariff = 20.0
        self.created_at = datetime.now().strftime("%Y-%m-%d")
        self.lat = 52.0
        self.lng = 4.0


