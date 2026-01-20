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

_VALID_PAYMENT_STATUSES = {"unpaid", "pending", "paid", "failed"}
_VALID_STATUSES = {"pending", "confirmed", "cancelled"}
_VALID_ROLES = {"USER", "ADMIN"}


def get_connection(db_path: str = None) -> sqlite3.Connection:
    """
    Open a connection to the SQLite database at db_path.
    Enables foreign key constraints.
    """
    if db_path is None:
        # Use path relative to this file's location
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'MobyPark.db')
    con = sqlite3.connect(db_path)
    # Make rows accessible like dicts if you want (optional)
    con.row_factory = sqlite3.Row
    # Enforce foreign keys
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def get_db():
    con = get_connection()
    try:
        yield con
    finally:
        try:
            con.close()
        except Exception:
            pass


def record_exists(con: sqlite3.Connection, table: str, where: dict) -> bool:
    """
    Check of er al een record bestaat in `table` dat voldoet aan de waarden in `where`.

    Parameters:
        con   - open sqlite3.Connection
        table - naam van de tabel (string)
        where - dict met kolomnamen en waarden om op te filteren

    Returns:
        True als er minstens één record bestaat, anders False
    """
    con.execute("PRAGMA foreign_keys = ON;")

    if not where:
        raise ValueError("where mag niet leeg zijn.")

    conditions = " AND ".join([f"{col} = :{col}" for col in where.keys()])
    sql = f"SELECT 1 FROM {table} WHERE {conditions} LIMIT 1"

    cur = con.execute(sql, where)
    return cur.fetchone() is not None


def insert_parking_lot(con: sqlite3.Connection, lot_obj) -> int:
    """
    Insert a parking lot into the `parking_lots` table.

    Accepts either a dict or an object with attributes:
      id, name, location, address, capacity, reserved, tariff, daytariff, created_at,
      coordinates = { lat, lng }  (or top-level lat/lng)

    Returns the inserted row id.
    """

    con.execute("PRAGMA foreign_keys = ON;")

    # Helper to support dicts or objects
    def _get(src, key, default=None):
        if isinstance(src, dict):
            return src.get(key, default)
        return getattr(src, key, default)

    # Pull/normalize fields
    try:
        rec_id = None if _get(lot_obj, "id") in (
            None, "") else int(_get(lot_obj, "id"))
        name = _get(lot_obj, "name") or ""
        location = _get(lot_obj, "location")
        address = _get(lot_obj, "address")
        capacity = int(_get(lot_obj, "capacity"))
        reserved = int(_get(lot_obj, "reserved", 0))
        tariff = float(_get(lot_obj, "tariff"))
        daytariff = float(_get(lot_obj, "daytariff"))
        created_at = _get(lot_obj, "created_at")  # expects YYYY-MM-DD

        coords = _get(lot_obj, "coordinates", {}) or {}
        lat = _get(lot_obj, "lat", _get(coords, "lat"))
        lng = _get(lot_obj, "lng", _get(coords, "lng"))
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        raise ValueError(
            "Numeric fields (id, capacity, reserved, tariff, daytariff, lat, lng) must be valid numbers.")

    # Validations
    if not name:
        raise ValueError("name is required.")
    if capacity < 0:
        raise ValueError("capacity cannot be negative.")
    if reserved < 0 or reserved > capacity:
        raise ValueError("reserved must be between 0 and capacity.")
    if tariff < 0 or daytariff < 0:
        raise ValueError("tariff and daytariff must be non-negative.")
    # Date check (YYYY-MM-DD)
    try:
        datetime.strptime(created_at, "%Y-%m-%d")
    except Exception:
        raise ValueError(f"created_at must be YYYY-MM-DD; got '{created_at}'.")

    payload = {
        "id": rec_id,
        "name": name,
        "location": location,
        "address": address,
        "capacity": capacity,
        "reserved": reserved,
        "tariff": tariff,
        "daytariff": daytariff,
        "created_at": created_at,
        "lat": lat,
        "lng": lng,
    }

    sql = """
    INSERT INTO parking_lots
      (id, name, location, address, capacity, reserved, tariff, daytariff, created_at, lat, lng)
    VALUES
      (:id, :name, :location, :address, :capacity, :reserved, :tariff, :daytariff, :created_at, :lat, :lng)
    """

    with con:
        cur = con.execute(sql, payload)
        return cur.lastrowid


def get_all_parking_lots(con: sqlite3.Connection):
    """
    Haal alle records op uit de tabel `parking_lots`.

    Parameters:
        con - open sqlite3.Connection

    Returns:
        Lijst van dicts, elk representerend een record.
    """
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM parking_lots"
    cur = con.execute(sql)
    rows = cur.fetchall()
    return [Parking_lots_model.from_dict(dict(row)) for row in rows]


def get_parking_lot_by_id(con: sqlite3.Connection, lot_id: int):
    """
    Haal een record op uit de tabel `parking_lots` op basis van het id.

    Parameters:
        con    - open sqlite3.Connection
        lot_id - id van de parking lot (int)

    Returns:
        Een dict representerend het record, of None als niet gevonden.
    """
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM parking_lots WHERE id = ?"
    cur = con.execute(sql, (lot_id,))
    row = cur.fetchone()
    if row:
        return Parking_lots_model.from_dict(dict(row))
    return None


def insert_user(con: sqlite3.Connection, user_obj) -> int:
    con.execute("PRAGMA foreign_keys = ON;")

    # Extract values
    try:
        rec_id = None if user_obj.id in (None, "") else int(user_obj.id)
        username = str(user_obj.username)
        password = str(user_obj.password)
        name = getattr(user_obj, "name", None)
        email = getattr(user_obj, "email", None)
        phone = getattr(user_obj, "phone", None)
        role = (user_obj.role or "USER").upper()
        created_at = str(user_obj.created_at)
        birth_year = None if user_obj.birth_year in (
            None, "") else int(user_obj.birth_year)
        active = 1 if bool(user_obj.active) else 0
    except Exception as e:
        raise ValueError(f"Invalid field types for user object: {e}")

    # Validations
    if not username:
        raise ValueError("username is required.")
    if not password:
        raise ValueError("password is required.")
    if role not in _VALID_ROLES:
        raise ValueError(f"role must be one of {_VALID_ROLES}, got '{role}'.")
    try:
        datetime.strptime(created_at, "%Y-%m-%d")
    except Exception:
        raise ValueError(f"created_at must be YYYY-MM-DD, got '{created_at}'.")

    payload = {
        "id": rec_id,
        "username": username,
        "password": password,
        "name": name,
        "email": email,
        "phone": phone,
        "role": role,
        "created_at": created_at,
        "birth_year": birth_year,
        "active": active,
    }

    sql = """
    INSERT INTO users
      (id, username, password, name, email, phone, role, created_at, birth_year, active)
    VALUES
      (:id, :username, :password, :name, :email, :phone, :role, :created_at, :birth_year, :active)
    """

    with con:
        cur = con.execute(sql, payload)
        return cur.lastrowid


def get_all_users(con: sqlite3.Connection):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM users"
    cur = con.execute(sql)
    rows = cur.fetchall()
    return [User_model.from_dict(**dict(row)) for row in rows]


def get_user_by_id(con: sqlite3.Connection, user_id: int):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM users WHERE id = ?"
    cur = con.execute(sql, (user_id,))
    row = cur.fetchone()
    if row:
        return User_model.from_dict(**dict(row))
    return None


def get_users_by_username(con: sqlite3.Connection, username: str):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM users WHERE username = ?"
    cur = con.execute(sql, (username,))
    user = cur.fetchone()
    if user:
        return User_model.from_dict(**dict(user))
    return None


def get_users_by_name(con: sqlite3.Connection, name: str):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM users WHERE name = ?"
    cur = con.execute(sql, (name,))
    rows = cur.fetchall()
    if rows:
        return [User_model.from_dict(**dict(row)) for row in rows]
    return None


def get_users_by_email(con: sqlite3.Connection, email: str):
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM users WHERE email = ?"
    cur = con.execute(sql, (email,))
    rows = cur.fetchall()
    if rows:
        return [User_model.from_dict(**dict(row)) for row in rows]
    return None


def insert_vehicle(con: sqlite3.Connection, vehicle_obj) -> int:
    """
    Insert a vehicle into the `vehicles` table.

    Expects an object with attributes:
      id, user_id, license_plate, make, model, color, year, created_at (YYYY-MM-DD)

    Returns the inserted row id.
    Raises ValueError for validation issues and sqlite3.IntegrityError for FK/PK conflicts.
    """
    con.execute("PRAGMA foreign_keys = ON;")

    try:
        rec_id = None if vehicle_obj.id in (None, "") else int(vehicle_obj.id)
        user_id = int(vehicle_obj.user_id)
        license_plate = str(vehicle_obj.license_plate)
        make = getattr(vehicle_obj, "make", None)
        model = getattr(vehicle_obj, "model", None)
        color = getattr(vehicle_obj, "color", None)
        year = None if vehicle_obj.year in (
            None, "") else int(vehicle_obj.year)
        created_at = str(vehicle_obj.created_at)
    except Exception as e:
        raise ValueError(f"Invalid field types for vehicle object: {e}")

    # Validations
    if not license_plate:
        raise ValueError("license_plate is required.")
    if year is not None and year < 1886:  # first car invention year 😉
        raise ValueError("year must be >= 1886 if provided.")
    try:
        datetime.strptime(created_at, "%Y-%m-%d")
    except Exception:
        raise ValueError(f"created_at must be YYYY-MM-DD, got '{created_at}'.")

    payload = {
        "id": rec_id,
        "user_id": user_id,
        "license_plate": license_plate,
        "make": make,
        "model": model,
        "color": color,
        "year": year,
        "created_at": created_at,
    }

    sql = """
    INSERT INTO vehicles
      (id, user_id, license_plate, make, model, color, year, created_at)
    VALUES
      (:id, :user_id, :license_plate, :make, :model, :color, :year, :created_at)
    """

    with con:
        cur = con.execute(sql, payload)
        return cur.lastrowid


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


def insert_reservation(con: sqlite3.Connection, reservation_obj) -> int:
    """
    Insert a reservation into the `reservations` table.

    Expects a dict or object with attributes:
      id, user_id, parking_lot_id, vehicle_id,
      start_time, end_time, status, created_at, cost

    Returns the inserted row id.
    Raises ValueError for validation issues and sqlite3.IntegrityError for FK/PK conflicts.
    """
    con.execute("PRAGMA foreign_keys = ON;")

    def _get(src, key, default=None):
        if isinstance(src, dict):
            return src.get(key, default)
        return getattr(src, key, default)

    # Parse fields
    try:
        rec_id = None if _get(reservation_obj, "id") in (
            None, "") else int(_get(reservation_obj, "id"))
        user_id = int(_get(reservation_obj, "user_id"))
        parking_lot_id = int(_get(reservation_obj, "parking_lot_id"))
        vehicle_id = int(_get(reservation_obj, "vehicle_id"))
        cost = float(_get(reservation_obj, "cost"))
    except (TypeError, ValueError):
        raise ValueError(
            "id, user_id, parking_lot_id, vehicle_id must be integers; cost must be numeric.")

    status = (_get(reservation_obj, "status") or "").lower()
    created_at = _get(reservation_obj, "created_at")
    start_time = _get(reservation_obj, "start_time")
    end_time = _get(reservation_obj, "end_time")

    # Validations
    if status not in _VALID_STATUSES:
        raise ValueError(
            f"status must be one of {_VALID_STATUSES}, got '{status}'.")
    if cost < 0:
        raise ValueError("cost must be non-negative.")

    # Basic ISO8601 checks
    def _check_iso(ts: str, field: str):
        try:
            if ts.endswith("Z"):
                datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
            else:
                datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            raise ValueError(
                f"{field} must be ISO8601 (e.g. 2025-12-03T11:00:00Z), got '{ts}'.")

    _check_iso(start_time, "start_time")
    _check_iso(end_time, "end_time")
    _check_iso(created_at, "created_at")

    payload = {
        "id": rec_id,
        "user_id": user_id,
        "parking_lot_id": parking_lot_id,
        "vehicle_id": vehicle_id,
        "start_time": start_time,
        "end_time": end_time,
        "status": status,
        "created_at": created_at,
        "cost": cost,
    }

    sql = """
    INSERT INTO reservations
      (id, user_id, parking_lot_id, vehicle_id, start_time, end_time, status, created_at, cost)
    VALUES
      (:id, :user_id, :parking_lot_id, :vehicle_id, :start_time, :end_time, :status, :created_at, :cost)
    """

    with con:
        cur = con.execute(sql, payload)
        return cur.lastrowid


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


def insert_parking_session(con: sqlite3.Connection, session_obj) -> int:
    """
    Insert a parking session into the `sessions` table.

    Expects an object with attributes:
      parking_lot_id, user_id, vehicle_id (optional), started, stopped (optional),
      duration_minutes (optional), payment_status (optional)

    Returns the auto-generated session_id (int).
    Raises ValueError for validation issues and sqlite3.IntegrityError for FK/PK conflicts.
    """
    con.execute("PRAGMA foreign_keys = ON;")

    # --- Parse & validate ---
    try:
        lot_id = int(session_obj.parking_lot_id)
        user_id = int(session_obj.user_id)
        vehicle_id = None if not hasattr(session_obj, 'vehicle_id') or session_obj.vehicle_id in (
            None, "") else int(session_obj.vehicle_id)
        duration = None if not hasattr(session_obj, 'duration_minutes') or session_obj.duration_minutes in (
            None, "") else int(session_obj.duration_minutes)
    except (TypeError, ValueError):
        raise ValueError(
            "parking_lot_id, user_id, vehicle_id, and duration_minutes must be numeric when provided.")

    payment_status = getattr(
        session_obj, 'payment_status', 'unpaid') or "unpaid"
    if payment_status and payment_status.lower() not in _VALID_PAYMENT_STATUSES:
        raise ValueError(
            f"payment_status must be one of {_VALID_PAYMENT_STATUSES}, got '{payment_status}'.")

    if duration is not None and duration < 0:
        raise ValueError("duration_minutes cannot be negative.")

    started = getattr(session_obj, 'started', None)
    stopped = getattr(session_obj, 'stopped', None)

    # --- Build payload ---
    payload = {
        "parking_lot_id": lot_id,
        "user_id": user_id,
        "vehicle_id": vehicle_id,
        "started": started,
        "stopped": stopped,
        "duration_minutes": duration,
        "payment_status": payment_status,
    }

    sql = """
    INSERT INTO sessions
      (parking_lot_id, user_id, vehicle_id, started, stopped, duration_minutes, payment_status)
    VALUES
      (:parking_lot_id, :user_id, :vehicle_id, :started, :stopped, :duration_minutes, :payment_status)
    """

    with con:
        cur = con.execute(sql, payload)
        return cur.lastrowid  # returns session_id

    """
    Insert a parking session into the `parking_sessions` table.

    Expects an object with attributes:
      id, parking_lot_id, licenseplate, started, stopped, user,
      duration_minutes, cost, payment_status

    Returns the inserted row id (int).
    Raises ValueError for validation issues and sqlite3.IntegrityError for FK/PK conflicts.
    """
    # Ensure FK constraints are enforced for this connection
    con.execute("PRAGMA foreign_keys = ON;")

    # Basic validations / normalization
    try:
        rec_id = None if session_obj.id in (None, "") else int(session_obj.id)
        lot_id = int(session_obj.parking_lot_id)
        duration = None if session_obj.duration_minutes in (
            None, "") else int(session_obj.duration_minutes)
        cost = None if session_obj.cost in (
            None, "") else float(session_obj.cost)
    except (TypeError, ValueError):
        raise ValueError(
            "id, parking_lot_id, duration_minutes, and cost must be numeric when provided.")

    payment_status = (session_obj.payment_status or "").lower()
    if payment_status not in _VALID_PAYMENT_STATUSES:
        raise ValueError(
            f"payment_status must be one of {_VALID_PAYMENT_STATUSES}, got '{session_obj.payment_status}'.")

    if duration is not None and duration < 0:
        raise ValueError("duration_minutes cannot be negative.")
    if cost is not None and cost < 0:
        raise ValueError("cost cannot be negative.")

    # (Optional) sanity check ISO8601 timestamps
    def _check_iso8601(ts: str, field: str):
        if ts is None:
            return
        try:
            # Accepts forms like '2020-03-25T20:29:47Z' or with offset '+00:00'
            if ts.endswith("Z"):
                datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
            else:
                # very light check; adjust if you want stricter parsing
                datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            raise ValueError(
                f"{field} must be ISO8601 (e.g., 2020-03-25T20:29:47Z); got '{ts}'.")

    _check_iso8601(session_obj.started, "started")
    _check_iso8601(session_obj.stopped, "stopped")

    # Build payload (note DB column is license_plate, object has licenseplate)
    payload = {
        "id": rec_id,  # can be None to auto-assign if column defined AUTOINCREMENT; with INTEGER PRIMARY KEY it's fine too
        "parking_lot_id": lot_id,
        "licenseplate": session_obj.licenseplate,
        "started": session_obj.started,
        "stopped": session_obj.stopped,
        "user": session_obj.user,
        "duration_minutes": duration,
        "cost": cost,
        "payment_status": payment_status,
    }

    sql = """
    INSERT INTO parking_sessions
      (id, parking_lot_id, licenseplate, started, stopped, user, duration_minutes, cost, payment_status)
    VALUES
      (:id, :parking_lot_id, :licenseplate, :started, :stopped, :user, :duration_minutes, :cost, :payment_status)
    """

    with con:
        cur = con.execute(sql, payload)
        # If id was provided, SQLite returns that; if None, rowid is generated
        return cur.lastrowid


def insert_payment(con: sqlite3.Connection, payment_obj) -> int:
    """
    Insert a payment into the `payments` table.

    Expects a dict or object with attributes:
      id, transaction (or transaction_id), amount, initiator, created_at,
      completed, hash, t_amount, t_date, t_method, t_issuer, t_bank

    - Accepts created_at/completed/t_date as:
        * ISO8601 (e.g. 2025-12-03T11:00:00Z)  -> kept as-is
        * 'DD-MM-YYYY HH:MM:UNIX'              -> converted to ISO8601 using the UNIX
        * plain UNIX (10 or 13 digits)         -> converted to ISO8601 (UTC)
        * 'DD-MM-YYYY HH:MM'                   -> converted to ISO8601 with :00 seconds (UTC)

    Returns the inserted row id.
    Raises ValueError for validation issues and sqlite3.IntegrityError for FK/PK conflicts.
    """
    con.execute("PRAGMA foreign_keys = ON;")

    def _get(src, key, default=None):
        if isinstance(src, dict):
            return src.get(key, default)
        return getattr(src, key, default)

    # --- converters ---------------------------------------------------------
    def _to_iso8601(s: str) -> str:
        """
        Convert 'DD-MM-YYYY HH:MM:UNIX' or plain UNIX (10/13 digits) to ISO8601 UTC.
        If no UNIX is found, try 'DD-MM-YYYY HH:MM' as UTC.
        """
        s = str(s).strip()
        # Use trailing UNIX if present (10 or 13 digits)
        m = re.search(r'(\d{10}|\d{13})$', s)
        if m:
            ts = int(m.group(1))
            if len(m.group(1)) == 13:  # milliseconds
                ts //= 1000
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # Fallback: parse 'DD-MM-YYYY HH:MM' (first 16 chars), assume UTC
        dt = datetime.strptime(
            s[:16], "%d-%m-%Y %H:%M").replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _normalize_iso(ts):
        """Return ts as ISO8601 Z. If already ISO8601, keep; otherwise try to convert."""
        if not ts:
            return ts
        ts = str(ts).strip()
        try:
            # already ISO with Z?
            if ts.endswith("Z"):
                datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
                return ts
            # already ISO without Z (or with offset)?
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return ts
        except Exception:
            # try to coerce DD-MM-YYYY/UNIX hybrid or plain UNIX
            return _to_iso8601(ts)

    # -----------------------------------------------------------------------

    # Parse fields
    try:
        pay_id = None if _get(payment_obj, "id") in (
            None, "") else int(_get(payment_obj, "id"))
        transaction_id = str(_get(payment_obj, "transaction")
                             or _get(payment_obj, "transaction_id"))
        amount = float(_get(payment_obj, "amount"))
        t_amount = None if _get(payment_obj, "t_amount") in (
            None, "") else float(_get(payment_obj, "t_amount"))
    except (TypeError, ValueError):
        raise ValueError(
            "id must be integer; amount/t_amount must be numeric.")

    initiator = str(_get(payment_obj, "initiator") or "")
    created_at = _normalize_iso(_get(payment_obj, "created_at"))
    completed = _normalize_iso(_get(payment_obj, "completed"))
    hash_val = str(_get(payment_obj, "hash") or "")
    t_date = _normalize_iso(_get(payment_obj, "t_date"))
    t_method = _get(payment_obj, "t_method")
    t_issuer = _get(payment_obj, "t_issuer")
    t_bank = _get(payment_obj, "t_bank")

    # Basic validations
    if not transaction_id:
        raise ValueError("transaction_id cannot be empty.")
    if amount < 0:
        raise ValueError("amount must be non-negative.")
    if not initiator:
        raise ValueError("initiator cannot be empty.")
    if not hash_val:
        raise ValueError("hash cannot be empty.")

    # Final ISO8601 checks for timestamps
    def _check_iso(ts: str, field: str):
        if not ts:
            return
        try:
            if ts.endswith("Z"):
                datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
            else:
                datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            raise ValueError(
                f"{field} must be ISO8601 (e.g. 2025-12-03T11:00:00Z), got '{ts}'.")

    _check_iso(created_at, "created_at")
    _check_iso(completed, "completed")
    _check_iso(t_date, "t_date")

    payload = {
        "id": pay_id,
        "transaction_id": transaction_id,
        "amount": amount,
        "initiator": initiator,
        "created_at": created_at,
        "completed": completed,
        "hash": hash_val,
        "t_amount": t_amount,
        "t_date": t_date,
        "t_method": t_method,
        "t_issuer": t_issuer,
        "t_bank": t_bank,
    }

    sql = """
    INSERT INTO payments
      (id, transaction_id, amount, initiator, created_at, completed, hash,
       t_amount, t_date, t_method, t_issuer, t_bank)
    VALUES
      (:id, :transaction_id, :amount, :initiator, :created_at, :completed, :hash,
       :t_amount, :t_date, :t_method, :t_issuer, :t_bank)
    """

    with con:
        cur = con.execute(sql, payload)
        return cur.lastrowid


def insert_payments_bulk(conn: sqlite3.Connection, payments, chunk_size: int = 1000):
    # 1) Snellere schrijfinstellingen (veilig genoeg voor de meeste loads)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")

    # 2) Voorbereide statement (met UPSERT op unieke transaction_id)
    sql = """
    INSERT INTO payments (
        transaction_id, amount, initiator, created_at, completed, hash,
        t_amount, t_date, t_method, t_issuer, t_bank
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(transaction_id) DO UPDATE SET
        amount=excluded.amount,
        initiator=excluded.initiator,
        created_at=excluded.created_at,
        completed=excluded.completed,
        hash=excluded.hash,
        t_amount=excluded.t_amount,
        t_date=excluded.t_date,
        t_method=excluded.t_method,
        t_issuer=excluded.t_issuer,
        t_bank=excluded.t_bank;
    """

    # 3) Maak tuples van je objecten/dicts (dit is snel voor executemany)
    def val(src, key, default=None):
        return src.get(key, default) if isinstance(src, dict) else getattr(src, key, default)

    rows = []
    for p in payments:
        rows.append((
            val(p, "transaction_id") or val(p, "transaction"),
            float(val(p, "amount") or 0),
            val(p, "initiator"),
            val(p, "created_at"),
            val(p, "completed"),
            val(p, "hash"),
            val(p, "t_amount"),
            val(p, "t_date"),
            val(p, "t_method"),
            val(p, "t_issuer"),
            val(p, "t_bank"),
        ))

    # 4) Eén transactie voor alle batches
    with conn:  # -> BEGIN ... COMMIT één keer
        for i in range(0, len(rows), chunk_size):
            conn.executemany(sql, rows[i:i+chunk_size])


# ================= HELPER FUNCTIONS =================

def get_user_id_by_username(con: sqlite3.Connection, username: str):
    """
    Get user ID by username.

    Parameters:
        con      - open sqlite3.Connection
        username - username string

    Returns:
        User ID (int) or None if not found
    """
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT id FROM users WHERE username = ?"
    cur = con.execute(sql, (username,))
    row = cur.fetchone()
    return row["id"] if row else None


def get_session_by_id(con: sqlite3.Connection, session_id: int):
    """
    Get a parking session by ID.

    Parameters:
        con        - open sqlite3.Connection
        session_id - session ID (int)

    Returns:
        Dict representing the session or None if not found
    """
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM sessions WHERE session_id = ?"
    cur = con.execute(sql, (session_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def get_sessions_by_parking_lot(con: sqlite3.Connection, parking_lot_id: int):
    """
    Get all sessions for a parking lot.

    Parameters:
        con            - open sqlite3.Connection
        parking_lot_id - parking lot ID (int)

    Returns:
        List of dicts representing sessions
    """
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM sessions WHERE parking_lot_id = ?"
    cur = con.execute(sql, (parking_lot_id,))
    rows = cur.fetchall()
    return [dict(row) for row in rows]


def get_sessions_by_user_id(con: sqlite3.Connection, user_id: int):
    """
    Get all sessions for a user.

    Parameters:
        con     - open sqlite3.Connection
        user_id - user ID (int)

    Returns:
        List of dicts representing sessions
    """
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM sessions WHERE user_id = ?"
    cur = con.execute(sql, (user_id,))
    rows = cur.fetchall()
    return [dict(row) for row in rows]


def get_payments_by_user_id(con: sqlite3.Connection, user_id: int):
    """
    Get all payments for a user.

    Parameters:
        con     - open sqlite3.Connection
        user_id - user ID (int)

    Returns:
        List of dicts representing payments
    """
    con.execute("PRAGMA foreign_keys = ON;")
    sql = "SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC"
    cur = con.execute(sql, (user_id,))
    rows = cur.fetchall()
    return [dict(row) for row in rows]


# ================= UPDATE FUNCTIONS =================

def update_user(con: sqlite3.Connection, username: str, updates: dict) -> bool:
    """
    Update user fields.

    Parameters:
        con      - open sqlite3.Connection
        username - username of the user to update
        updates  - dict with field names and new values

    Returns:
        True if updated, False if user not found
    """
    con.execute("PRAGMA foreign_keys = ON;")

    # Check if user exists
    cur = con.execute("SELECT 1 FROM users WHERE username = ?", (username,))
    if not cur.fetchone():
        return False

    # Build dynamic UPDATE statement
    allowed_fields = ["name", "password", "email",
                      "phone", "role", "birth_year", "active"]
    fields_to_update = {k: v for k, v in updates.items(
    ) if k in allowed_fields and v is not None}

    if not fields_to_update:
        return True  # No valid fields to update

    set_clause = ", ".join(
        [f"{field} = ?" for field in fields_to_update.keys()])
    sql = f"UPDATE users SET {set_clause} WHERE username = ?"

    values = list(fields_to_update.values()) + [username]

    with con:
        con.execute(sql, values)

    return True


def update_parking_lot(con: sqlite3.Connection, lot_id: int, updates: dict) -> bool:
    """
    Update parking lot fields.

    Parameters:
        con     - open sqlite3.Connection
        lot_id  - parking lot ID
        updates - dict with field names and new values

    Returns:
        True if updated, False if parking lot not found
    """
    con.execute("PRAGMA foreign_keys = ON;")

    # Check if parking lot exists
    cur = con.execute("SELECT 1 FROM parking_lots WHERE id = ?", (lot_id,))
    if not cur.fetchone():
        return False

    # Build dynamic UPDATE statement
    allowed_fields = ["name", "location", "address", "capacity",
                      "reserved", "tariff", "daytariff", "lat", "lng"]
    fields_to_update = {k: v for k, v in updates.items(
    ) if k in allowed_fields and v is not None}

    if not fields_to_update:
        return True

    set_clause = ", ".join(
        [f"{field} = ?" for field in fields_to_update.keys()])
    sql = f"UPDATE parking_lots SET {set_clause} WHERE id = ?"

    values = list(fields_to_update.values()) + [lot_id]

    with con:
        con.execute(sql, values)

    return True


def update_vehicle(con: sqlite3.Connection, vehicle_id: int, updates: dict) -> bool:
    """
    Update vehicle fields.

    Parameters:
        con        - open sqlite3.Connection
        vehicle_id - vehicle ID
        updates    - dict with field names and new values

    Returns:
        True if updated, False if vehicle not found
    """
    con.execute("PRAGMA foreign_keys = ON;")

    # Check if vehicle exists
    cur = con.execute("SELECT 1 FROM vehicles WHERE id = ?", (vehicle_id,))
    if not cur.fetchone():
        return False

    # Build dynamic UPDATE statement
    allowed_fields = ["license_plate", "make",
                      "model", "color", "year", "name", "updated_at"]
    fields_to_update = {k: v for k, v in updates.items(
    ) if k in allowed_fields and v is not None}

    if not fields_to_update:
        return True

    set_clause = ", ".join(
        [f"{field} = ?" for field in fields_to_update.keys()])
    sql = f"UPDATE vehicles SET {set_clause} WHERE id = ?"

    values = list(fields_to_update.values()) + [vehicle_id]

    with con:
        con.execute(sql, values)

    return True


def update_reservation(con: sqlite3.Connection, reservation_id: int, updates: dict) -> bool:
    """
    Update reservation fields.

    Parameters:
        con            - open sqlite3.Connection
        reservation_id - reservation ID
        updates        - dict with field names and new values

    Returns:
        True if updated, False if reservation not found
    """
    con.execute("PRAGMA foreign_keys = ON;")

    # Check if reservation exists
    cur = con.execute(
        "SELECT 1 FROM reservations WHERE id = ?", (reservation_id,))
    if not cur.fetchone():
        return False

    # Build dynamic UPDATE statement
    allowed_fields = ["user_id", "parking_lot_id", "vehicle_id", "start_time",
                      "duration", "status", "licenseplate", "startdate", "enddate", "parkinglot", "user"]
    fields_to_update = {k: v for k, v in updates.items(
    ) if k in allowed_fields and v is not None}

    if not fields_to_update:
        return True

    set_clause = ", ".join(
        [f"{field} = ?" for field in fields_to_update.keys()])
    sql = f"UPDATE reservations SET {set_clause} WHERE id = ?"

    values = list(fields_to_update.values()) + [reservation_id]

    with con:
        con.execute(sql, values)

    return True


def update_payment(con: sqlite3.Connection, transaction_id: str, updates: dict) -> bool:
    """
    Update payment fields.

    Parameters:
        con            - open sqlite3.Connection
        transaction_id - transaction ID
        updates        - dict with field names and new values

    Returns:
        True if updated, False if payment not found
    """
    con.execute("PRAGMA foreign_keys = ON;")

    # Check if payment exists
    cur = con.execute(
        "SELECT 1 FROM payments WHERE transaction_id = ?", (transaction_id,))
    if not cur.fetchone():
        return False

    # Build dynamic UPDATE statement
    allowed_fields = ["amount", "completed", "t_date",
                      "t_method", "t_issuer", "t_bank", "t_amount"]
    fields_to_update = {k: v for k, v in updates.items(
    ) if k in allowed_fields and v is not None}

    if not fields_to_update:
        return True

    set_clause = ", ".join(
        [f"{field} = ?" for field in fields_to_update.keys()])
    sql = f"UPDATE payments SET {set_clause} WHERE transaction_id = ?"

    values = list(fields_to_update.values()) + [transaction_id]

    with con:
        con.execute(sql, values)

    return True


def update_session(con: sqlite3.Connection, session_id: int, updates: dict) -> bool:
    """
    Update parking session fields.

    Parameters:
        con        - open sqlite3.Connection
        session_id - session ID
        updates    - dict with field names and new values

    Returns:
        True if updated, False if session not found
    """
    con.execute("PRAGMA foreign_keys = ON;")

    # Check if session exists
    cur = con.execute(
        "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,))
    if not cur.fetchone():
        return False

    # Build dynamic UPDATE statement
    allowed_fields = ["parking_lot_id", "user_id", "started",
                      "duration_minutes", "payment_status", "stopped"]
    fields_to_update = {k: v for k, v in updates.items(
    ) if k in allowed_fields and v is not None}

    if not fields_to_update:
        return True

    set_clause = ", ".join(
        [f"{field} = ?" for field in fields_to_update.keys()])
    sql = f"UPDATE sessions SET {set_clause} WHERE session_id = ?"

    values = list(fields_to_update.values()) + [session_id]

    with con:
        con.execute(sql, values)

    return True


# ================= DELETE FUNCTIONS =================

def delete_parking_lot(con: sqlite3.Connection, lot_id: int) -> bool:
    """
    Delete a parking lot by ID.

    Parameters:
        con    - open sqlite3.Connection
        lot_id - parking lot ID

    Returns:
        True if deleted, False if not found
    """
    con.execute("PRAGMA foreign_keys = ON;")

    cur = con.execute("SELECT 1 FROM parking_lots WHERE id = ?", (lot_id,))
    if not cur.fetchone():
        return False

    with con:
        con.execute("DELETE FROM parking_lots WHERE id = ?", (lot_id,))

    return True


def delete_vehicle(con: sqlite3.Connection, vehicle_id: int) -> bool:
    """
    Delete a vehicle by ID.

    Parameters:
        con        - open sqlite3.Connection
        vehicle_id - vehicle ID

    Returns:
        True if deleted, False if not found
    """
    con.execute("PRAGMA foreign_keys = ON;")

    cur = con.execute("SELECT 1 FROM vehicles WHERE id = ?", (vehicle_id,))
    if not cur.fetchone():
        return False

    with con:
        con.execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id,))

    return True


def delete_reservation(con: sqlite3.Connection, reservation_id: int) -> bool:
    """
    Delete a reservation by ID.

    Parameters:
        con            - open sqlite3.Connection
        reservation_id - reservation ID

    Returns:
        True if deleted, False if not found
    """
    con.execute("PRAGMA foreign_keys = ON;")

    cur = con.execute(
        "SELECT 1 FROM reservations WHERE id = ?", (reservation_id,))
    if not cur.fetchone():
        return False

    with con:
        con.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))

    return True


def delete_session(con: sqlite3.Connection, session_id: int) -> bool:
    """
    Delete a parking session by ID.

    Parameters:
        con        - open sqlite3.Connection
        session_id - session ID

    Returns:
        True if deleted, False if not found
    """
    con.execute("PRAGMA foreign_keys = ON;")

    cur = con.execute(
        "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,))
    if not cur.fetchone():
        return False

    with con:
        con.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

    return True


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
