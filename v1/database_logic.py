import sqlite3
from datetime import datetime

_VALID_PAYMENT_STATUSES = {"unpaid", "pending", "paid", "failed"}


def get_connection(db_path: str) -> sqlite3.Connection:
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
