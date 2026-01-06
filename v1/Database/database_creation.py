# create_db.py
import sqlite3
from pathlib import Path


def create_database(db_path="v1/Database/MobyPark.db"):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        cur = conn.cursor()

        # Users
        cur.execute("""
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

        # Auth sessions
        cur.execute("""
        CREATE TABLE IF NOT EXISTS auth_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)

        # Parking lots
        cur.execute("""
        CREATE TABLE IF NOT EXISTS parking_lots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            address TEXT NOT NULL,
            capacity INTEGER NOT NULL,
            reserved INTEGER NOT NULL,         -- 0/1 als boolean
            tariff REAL NOT NULL,
            daytariff INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL
        );
        """)

        # Vehicles
        cur.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_plate TEXT NOT NULL UNIQUE,
            make TEXT NOT NULL,
            model TEXT NOT NULL,
            color TEXT NOT NULL,
            year INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        """)

        # Sessions
        cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            parking_lot_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            vehicle_id INTEGER,
            started TEXT NOT NULL,
            stopped TEXT,
            duration_minutes INTEGER NOT NULL,
            payment_status TEXT NOT NULL,
            FOREIGN KEY (parking_lot_id) REFERENCES parking_lots(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE SET NULL
        );
        """)

        # Reservations
        cur.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
            user_id INTEGER NOT NULL,
            parking_lot_id INTEGER NOT NULL,
            vehicle_id INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            duration INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (parking_lot_id) REFERENCES parking_lots(id) ON DELETE CASCADE,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
        );
        """)

        # Payments
        cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT NOT NULL,          -- aangepast
            amount REAL NOT NULL,
            user_id INTEGER NOT NULL,
            session_id INTEGER NOT NULL,
            parking_lot_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            completed INTEGER NOT NULL,
            hash TEXT NOT NULL,
            t_date TEXT NOT NULL,
            t_method TEXT NOT NULL,
            t_issuer TEXT NOT NULL,
            t_bank TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
            FOREIGN KEY (parking_lot_id) REFERENCES parking_lots(id) ON DELETE CASCADE
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            vehicle_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
            UNIQUE (user_id, vehicle_id)
        );
        """)

        conn.commit()
        print(f"Database en tabellen aangemaakt in {db_path}")


if __name__ == "__main__":
    create_database()