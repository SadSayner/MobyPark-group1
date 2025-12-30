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




