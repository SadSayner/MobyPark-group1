import sqlite3
from datetime import datetime

_VALID_PAYMENT_STATUSES = {"unpaid", "pending", "paid", "failed"}
_VALID_STATUSES = {"pending", "confirmed", "cancelled"}
_VALID_ROLES = {"USER", "ADMIN"}


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


def insert_user(con: sqlite3.Connection, user_obj) -> int:
    """
    Insert a user into the `users` table.

    Expects an object with attributes:
      id, username, password, name, email, phone,
      role, created_at (YYYY-MM-DD), birth_year, active

    Returns the inserted row id.
    Raises ValueError for validation issues and sqlite3.IntegrityError for FK/PK conflicts.
    """
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


def insert_parking_session(con: sqlite3.Connection, session_obj) -> int:
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
        "license_plate": session_obj.licenseplate,
        "started": session_obj.started,
        "stopped": session_obj.stopped,
        "user": session_obj.user,
        "duration_minutes": duration,
        "cost": cost,
        "payment_status": payment_status,
    }

    sql = """
    INSERT INTO parking_sessions
      (id, parking_lot_id, license_plate, started, stopped, user, duration_minutes, cost, payment_status)
    VALUES
      (:id, :parking_lot_id, :license_plate, :started, :stopped, :user, :duration_minutes, :cost, :payment_status)
    """

    with con:
        cur = con.execute(sql, payload)
        # If id was provided, SQLite returns that; if None, rowid is generated
        return cur.lastrowid
