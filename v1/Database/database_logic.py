from datetime import datetime, timezone
import re
import sqlite3
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Models.parkinglots_model import Parking_lots_model  # noqa
from Models.user_model import User_model  # noqa
from Models.vehicle_model import Vehicle_model  # noqa
from Models.reservations_model import Reservations_model  # noqa

# Database logic functions


def get_connection(db_path: str = None) -> sqlite3.Connection:
    if db_path is None:
        db_path = 'v1\Database\MobyPark.db'
    """
    Open a connection to the SQLite database at db_path.
    Enables foreign key constraints.
    """
    con = sqlite3.connect(db_path)
    # Make rows accessible like dicts if you want (optional)
    con.row_factory = sqlite3.Row
    # Enforce foreign keys
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def wipe_table(con: sqlite3.Connection, table: str):
    """
    Delete all records from the specified table.

    Parameters:
        con   - open sqlite3.Connection
        table - naam van de tabel (string)
    """
    con.execute("PRAGMA foreign_keys = ON;")
    sql = f"DELETE FROM {table}"
    with con:
        con.execute(sql)

# Parkinglot functions


def get_all_parking_lots(con: sqlite3.Connection):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM parking_lots"
    cur = con.execute(sql)
    rows = cur.fetchall()
    return [Parking_lots_model.from_dict(**dict(row)) for row in rows]


def get_parking_lot_by_id(con: sqlite3.Connection, lot_id: int):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM parking_lots WHERE id = ?"
    cur = con.execute(sql, (lot_id,))
    row = cur.fetchone()
    if row:
        return Parking_lots_model.from_dict(**dict(row))
    return None


def get_all_users(con: sqlite3.Connection):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM users"
    cur = con.execute(sql)
    rows = cur.fetchall()
    return [User_model.from_dict(row) for row in rows]


def get_user_by_id(con: sqlite3.Connection, user_id: int):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM users WHERE id = ?"
    cur = con.execute(sql, (user_id,))
    row = cur.fetchone()
    if row:
        return User_model.from_dict(row)
    return None


def get_users_by_username(con: sqlite3.Connection, username: str):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM users WHERE username = ?"
    cur = con.execute(sql, (username,))
    user = cur.fetchone()
    if user:
        return User_model.from_dict(user)
    return None


def get_users_by_name(con: sqlite3.Connection, name: str):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM users WHERE name = ?"
    cur = con.execute(sql, (name,))
    rows = cur.fetchall()
    if rows:
        return [User_model.from_dict(row) for row in rows]
    return None


def get_users_by_email(con: sqlite3.Connection, email: str):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM users WHERE email = ?"
    cur = con.execute(sql, (email,))
    rows = cur.fetchall()
    if rows:
        return [User_model.from_dict(row) for row in rows]
    return None


def get_all_vehicles(con: sqlite3.Connection):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM vehicles"
    cur = con.execute(sql)
    rows = cur.fetchall()
    return [Vehicle_model.from_dict(row) for row in rows]


def get_vehicle_by_id(con: sqlite3.Connection, vehicle_id: int):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM vehicles WHERE id = ?"
    cur = con.execute(sql, (vehicle_id,))
    row = cur.fetchone()
    if row:
        return Vehicle_model.from_dict(row)
    return None


def get_vehicles_by_user_id(con: sqlite3.Connection, user_id: int):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM vehicles WHERE user_id = ?"
    cur = con.execute(sql, (user_id,))
    rows = cur.fetchall()
    if rows:
        return [Vehicle_model.from_dict(row) for row in rows]
    return None


def get_vehicles_by_license_plate(con: sqlite3.Connection, license_plate: str):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM vehicles WHERE license_plate = ?"
    cur = con.execute(sql, (license_plate,))
    rows = cur.fetchall()
    if rows:
        return [Vehicle_model.from_dict(row) for row in rows]
    return None


def get_all_reservations(con: sqlite3.Connection):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM reservations"
    cur = con.execute(sql)
    rows = cur.fetchall()
    return [Reservations_model.from_dict(row) for row in rows]


def get_reservation_by_id(con: sqlite3.Connection, reservation_id: int):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM reservations WHERE id = ?"
    cur = con.execute(sql, (reservation_id,))
    row = cur.fetchone()
    if row:
        return Reservations_model.from_dict(row)
    return None


def get_reservations_by_user_id(con: sqlite3.Connection, user_id: int):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM reservations WHERE user_id = ?"
    cur = con.execute(sql, (user_id,))
    rows = cur.fetchall()
    if rows:
        return [Reservations_model.from_dict(row) for row in rows]
    return None


def get_reservations_by_parking_lot_id(con: sqlite3.Connection, parking_lot_id: int):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM reservations WHERE parking_lot_id = ?"
    cur = con.execute(sql, (parking_lot_id,))
    rows = cur.fetchall()
    if rows:
        return [Reservations_model.from_dict(row) for row in rows]
    return None


def get_reservations_by_vehicle_id(con: sqlite3.Connection, vehicle_id: int):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM reservations WHERE vehicle_id = ?"
    cur = con.execute(sql, (vehicle_id,))
    rows = cur.fetchall()
    if rows:
        return [Reservations_model.from_dict(row) for row in rows]
    return None
