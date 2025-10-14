# db_batchinsert.py
# -----------------------------------------------------------
# Batch-inserts voor jouw SQLite schema.
# - Reservations: remap user_id via email (JSON user_id -> email -> DB MIN(id))
# - Users: INSERT OR IGNORE (email uniek), role default "USER"
# - Vehicles: accepteert user_id of username (lookup), INSERT OR IGNORE (kenteken uniek)
# - Payments: INSERT OR IGNORE op transaction_id (verondersteld uniek/PK)
# - Parking lots: coordinates.lat/lng → lat/lng
# - Per-rij afhandelen: fouten stoppen de batch niet
# -----------------------------------------------------------

from __future__ import annotations
import sqlite3
import re
from typing import Iterable, List, Dict, Any, Sequence, Tuple, Union, Set
from contextlib import contextmanager
from datetime import *
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from storage_utils import *  # noqa

Row = Dict[str, Any]
Rows = Iterable[Row]

# -------------------------- Utilities --------------------------


def to_list_of_dicts(data: Union[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [v for v in data.values() if isinstance(v, dict)]
    raise TypeError("Expected list[dict] or dict[str, dict]")


def _to_int_bool(v: Any) -> Any:
    return int(v) if isinstance(v, bool) else v


def _to_int(v: Any) -> Union[int, None]:
    if v is None:
        return None
    if isinstance(v, int):
        return v
    try:
        return int(str(v).strip())
    except Exception:
        return None


def _to_float(v: Any) -> Union[float, None]:
    if v is None:
        return None
    if isinstance(v, float):
        return v
    try:
        return float(str(v).strip())
    except Exception:
        return None


def _normalize_rows(rows: List[Row], fields: Sequence[str]) -> List[Tuple]:
    return [tuple(_to_int_bool(r.get(f)) for f in fields) for r in rows]


@contextmanager
def transaction(conn: sqlite3.Connection):
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("BEGIN;")
        yield
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise


def _batch_insert_per_row(
    conn: sqlite3.Connection,
    sql: str,
    rows: List[Tuple],
    *,
    debug: bool = False,
    debug_limit: int = 10
) -> Dict[str, int]:
    inserted = skipped = failed = 0
    cur = conn.cursor()
    shown = 0
    with transaction(conn):
        for params in rows:
            try:
                cur.execute(sql, params)
                rc = cur.rowcount
                if rc is None:
                    if cur.lastrowid:
                        inserted += 1
                    else:
                        skipped += 1
                else:
                    if rc > 0:
                        inserted += 1
                    else:
                        skipped += 1
            except (sqlite3.IntegrityError, sqlite3.OperationalError) as e:
                failed += 1
                if debug and shown < debug_limit:
                    print(f"[WARN] row failed: {params} -> {e}")
                    shown += 1
    return {"inserted": inserted, "skipped": skipped, "failed": failed}


def _require_fields(rows: List[Row], required: Sequence[str], *, debug: bool = False, debug_limit: int = 10) -> Tuple[List[Row], int]:
    ok: List[Row] = []
    missing = 0
    shown = 0
    for r in rows:
        miss = [k for k in required if r.get(k) is None]
        if miss:
            missing += 1
            if debug and shown < debug_limit:
                print(
                    f"[REQUIRE] ontbrekend: {miss} — aanwezige keys: {list(r.keys())}")
                shown += 1
        else:
            ok.append(r)
    return ok, missing


def _make_in_clause(n: int) -> str:
    return "(" + ",".join(["?"] * n) + ")"

# ---------------------- DateTime helpers --------------------


def calculate_duration(start_iso, end_iso):
    """
    Return duration in whole minutes between two ISO-like datetimes.
    Assumes 'YYYY-MM-DDTHH:MM:SSZ' or with %z offset; trims to seconds.
    """
    try:
        start_time = datetime.datetime.strptime(start_iso.replace(
            "Z", "+00:00"), "%Y-%m-%dT%H:%M:%S%z")
        start_time = datetime.datetime.strptime(start_time.strftime(
            '%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')

        end_time = datetime.datetime.strptime(end_iso.replace(
            "Z", "+00:00"), "%Y-%m-%dT%H:%M:%S%z")
        end_time = datetime.datetime.strptime(end_time.strftime(
            '%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
        minutes = int((end_time - start_time).total_seconds() / 60)
        return minutes
    except Exception:
        return None

# ---------------------- Users helpers (email remap) -----------------------


def extract_userid_to_email(users_source: Union[List[Row], Dict[str, Row]]) -> Dict[int, str]:
    """
    Build a map from the *JSON* users dataset: json_user_id -> email (first non-empty).
    """
    lod = to_list_of_dicts(users_source)
    result: Dict[int, str] = {}
    for u in lod:
        uid = _to_int(u.get("id"))
        email = (u.get("email") or "").strip() if u.get("email") else None
        if uid is not None and email:
            result.setdefault(uid, email)
    return result


def map_emails_to_db_user_ids(conn: sqlite3.Connection, emails: Set[str]) -> Dict[str, int]:
    """
    Map email -> MIN(id) in DB users (the 'first' user for that email).
    """
    if not emails:
        return {}
    cur = conn.cursor()
    placeholders = _make_in_clause(len(emails))
    sql = f"SELECT email, MIN(id) as id FROM users WHERE email IN {placeholders} GROUP BY email"
    cur.execute(sql, tuple(emails))
    return {row[0]: row[1] for row in cur.fetchall()}

# ------------------- USERS ------------------------------


USERS_FIELDS = ("username", "password", "name", "email", "phone",
                "role", "created_at", "birth_year", "active")

SQL_INSERT_USERS_IGNORE = f"""
INSERT OR IGNORE INTO users ({", ".join(USERS_FIELDS)})
VALUES ({", ".join("?" for _ in USERS_FIELDS)});
"""


def insert_users(conn: sqlite3.Connection, rows: Union[List[Row], Dict[str, Row]], *, debug: bool = False) -> Dict[str, int]:
    """
    Verwacht alle NOT NULL velden. Vult default role='USER' als niet gegeven.
    Email is UNIQUE in DB -> duplicates worden 'skipped' via OR IGNORE.
    """
    lod = to_list_of_dicts(rows)
    for r in lod:
        if r.get("role") in (None, ""):
            r["role"] = "USER"
        r["birth_year"] = _to_int(r.get("birth_year"))
        r["active"] = _to_int_bool(r.get("active"))
    rows_ok, missing = _require_fields(lod, USERS_FIELDS, debug=debug)
    data = _normalize_rows(rows_ok, USERS_FIELDS)
    result = _batch_insert_per_row(
        conn, SQL_INSERT_USERS_IGNORE, data, debug=debug)
    result["failed"] += missing
    return result

# ------------------- PARKING LOTS --------------------------


PARKING_FIELDS = ("name", "location", "address", "capacity",
                  "reserved", "tariff", "daytariff", "created_at", "lat", "lng")

SQL_INSERT_PARKING = f"""
INSERT OR IGNORE INTO parking_lots ({", ".join(PARKING_FIELDS)})
VALUES ({", ".join("?" for _ in PARKING_FIELDS)});
"""


def _dedupe_parking_lots(conn: sqlite3.Connection, *, debug: bool = True):
    cur = conn.cursor()
    conn.execute("PRAGMA foreign_keys=OFF;")
    try:
        cur.execute("""
            WITH groups AS (
              SELECT lower(trim(name)) AS k1,
                     lower(trim(address)) AS k2,
                     MIN(id) AS keep_id,
                     COUNT(*) AS cnt
              FROM parking_lots
              GROUP BY k1, k2
              HAVING cnt > 1
            )
            SELECT p.id AS dup_id, g.keep_id
            FROM parking_lots p
            JOIN groups g
              ON lower(trim(p.name)) = g.k1
             AND lower(trim(p.address)) = g.k2
            WHERE p.id <> g.keep_id
            ORDER BY g.keep_id, p.id;
        """)
        rows = cur.fetchall()
        if debug and rows:
            print(f"[PARKING-DEDUP] merging {len(rows)} duplicates")

        for dup_id, keep_id in rows:
            # repoint FKs that reference parking_lots(id)
            cur.execute(
                "UPDATE OR IGNORE sessions SET parking_lot_id=? WHERE parking_lot_id=?", (keep_id, dup_id))
            cur.execute(
                "UPDATE OR IGNORE reservations SET parking_lot_id=? WHERE parking_lot_id=?", (keep_id, dup_id))
            cur.execute(
                "UPDATE OR IGNORE payments SET parking_lot_id=? WHERE parking_lot_id=?", (keep_id, dup_id))
            cur.execute("DELETE FROM parking_lots WHERE id=?", (dup_id,))
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys=ON;")


def ensure_unique_index_parking_lots(conn: sqlite3.Connection):
    _dedupe_parking_lots(conn)
    cur = conn.cursor()
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_parking_lots_name_addr
        ON parking_lots (name COLLATE NOCASE, address COLLATE NOCASE);
    """)
    conn.commit()


def normalize_parking_rows(raw_rows: Union[List[Row], Dict[str, Row]]) -> List[Row]:
    lod = to_list_of_dicts(raw_rows)
    out: List[Row] = []
    for r in lod:
        coords = r.get("coordinates") or {}
        out.append({
            "name":       r.get("name"),
            "location":   r.get("location"),
            "address":    r.get("address"),
            "capacity":   _to_int(r.get("capacity")),
            "reserved":   _to_int(r.get("reserved")),
            "tariff":     _to_float(r.get("tariff")),
            "daytariff":  _to_int(r.get("daytariff")),
            "created_at": r.get("created_at"),
            "lat":        _to_float(coords.get("lat")),
            "lng":        _to_float(coords.get("lng")),
        })
    return out


def insert_parking_lots(conn: sqlite3.Connection, rows, *, debug: bool = False) -> Dict[str, int]:
    ensure_unique_index_parking_lots(conn)
    rows_norm = normalize_parking_rows(rows)
    rows_ok, missing = _require_fields(rows_norm, PARKING_FIELDS, debug=debug)
    data = _normalize_rows(rows_ok, PARKING_FIELDS)
    result = _batch_insert_per_row(conn, SQL_INSERT_PARKING, data, debug=debug)
    result["failed"] += missing
    return result


# ------------------- VEHICLES ----------------------------

VEHICLE_FIELDS = ("license_plate", "make", "model",
                  "color", "year", "created_at")

SQL_INSERT_VEHICLES_IGNORE = f"""
INSERT OR IGNORE INTO vehicles ({", ".join(VEHICLE_FIELDS)})
VALUES ({", ".join("?" for _ in VEHICLE_FIELDS)});
"""


def insert_vehicles(conn: sqlite3.Connection, rows: Union[List[Row], Dict[str, Row]], *, debug: bool = False) -> Dict[str, int]:
    """
    Insert vehicles zonder user_id. 
    Kenteken is UNIQUE -> OR IGNORE voorkomt duplicates.
    """
    lod = to_list_of_dicts(rows)
    for r in lod:
        r["year"] = _to_int(r.get("year"))

    rows_ok, missing = _require_fields(lod, VEHICLE_FIELDS, debug=debug)
    data = _normalize_rows(rows_ok, VEHICLE_FIELDS)
    result = _batch_insert_per_row(
        conn, SQL_INSERT_VEHICLES_IGNORE, data, debug=debug)
    result["failed"] += missing
    return result

# ------------------- PAYMENTS (FK-safe & initiator-prefer) ----------------


PAY_FIELDS = (
    "transaction_id", "amount", "user_id", "session_id", "parking_lot_id",
    "created_at", "completed", "hash", "t_date", "t_method", "t_issuer", "t_bank"
)

SQL_INSERT_PAYMENTS_IGNORE = f"""
INSERT OR IGNORE INTO payments ({", ".join(PAY_FIELDS)})
VALUES ({", ".join("?" for _ in PAY_FIELDS)});
"""


def _dedupe_payments_by_tx(conn: sqlite3.Connection, *, debug: bool = True):
    """
    Keep the oldest row per transaction_id, drop the rest.
    """
    cur = conn.cursor()
    # Drop exact duplicates leaving MIN(rowid)
    cur.execute("""
        DELETE FROM payments
        WHERE rowid NOT IN (
            SELECT MIN(rowid)
            FROM payments
            GROUP BY transaction_id
        )
    """)
    if debug:
        print(f"[PAY-DEDUP] after cleanup, kept one per transaction_id")
    conn.commit()


def ensure_unique_index_payments(conn: sqlite3.Connection):
    _dedupe_payments_by_tx(conn)
    cur = conn.cursor()
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_payments_tx
        ON payments (transaction_id);
    """)
    conn.commit()


def _parse_dt_lenient(s: Any) -> str | None:
    if not s:
        return None
    txt = str(s).strip()
    parts = txt.split(":")
    if len(parts) >= 3 and parts[-1].isdigit() and len(parts[-1]) >= 9:
        txt = ":".join(parts[:-1])  # strip trailing epoch
    from datetime import datetime
    patterns = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ]
    for p in patterns:
        try:
            if p.endswith("Z"):
                dt = datetime.strptime(txt.replace(
                    "Z", "+00:00"), "%Y-%m-%dT%H:%M:%S%z")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            dt = datetime.strptime(txt, p)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    return None


def _coerce_completed(val: Any) -> int:
    if isinstance(val, bool):
        return 1 if val else 0
    if isinstance(val, (int, float)):
        return 0 if float(val) == 0.0 else 1
    if val is None:
        return 0
    s = str(val).strip()
    if s == "":
        return 0
    if s.lower() in {"true", "yes", "y", "t", "completed", "done"}:
        return 1
    if _parse_dt_lenient(s):
        return 1
    return 1


def _map_usernames_to_user_ids(conn: sqlite3.Connection, usernames: Set[str]) -> Dict[str, int]:
    if not usernames:
        return {}
    cur = conn.cursor()
    cur.execute(
        f"SELECT username, id FROM users WHERE username IN {_make_in_clause(len(usernames))}",
        tuple(usernames)
    )
    return {row[0]: row[1] for row in cur.fetchall()}


def _db_has_user_id(conn: sqlite3.Connection, uid: int) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE id=? LIMIT 1;", (uid,))
    return cur.fetchone() is not None


def _db_has_session_id(conn: sqlite3.Connection, sid: int) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sessions WHERE session_id=? LIMIT 1;", (sid,))
    return cur.fetchone() is not None


def _db_has_parking_lot_id(conn: sqlite3.Connection, pid: int) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM parking_lots WHERE id=? LIMIT 1;", (pid,))
    return cur.fetchone() is not None

# (Optioneel) mapping van JSON sessions -> DB session_id via een bron-JSON


def _build_session_natural_key_map(sessions_source: Union[List[Row], Dict[str, Row]]) -> Dict[int, Tuple[Any, Any, Any, Any]]:
    """
    Maak map: json_session_id -> (user_id, parking_lot_id, vehicle_id, started)
    """
    lod = to_list_of_dicts(sessions_source)
    m: Dict[int, Tuple[Any, Any, Any, Any]] = {}
    for s in lod:
        sid = _to_int(s.get("session_id") or s.get("id"))
        if sid is None:
            continue
        key = (
            _to_int(s.get("user_id")),
            _to_int(s.get("parking_lot_id")),
            _to_int(s.get("vehicle_id")),
            s.get("started"),
        )
        m[sid] = key
    return m


def _db_find_session_id_by_key(conn: sqlite3.Connection, key: Tuple[Any, Any, Any, Any]) -> Union[int, None]:
    """
    Vind DB session_id via natuurlijke sleutel (user_id, parking_lot_id, vehicle_id, started).
    """
    u, p, v, started = key
    if None in (u, p, v) or not started:
        return None
    cur = conn.cursor()
    cur.execute(
        "SELECT session_id FROM sessions WHERE user_id=? AND parking_lot_id=? AND vehicle_id=? AND started=? LIMIT 1;",
        (u, p, v, started)
    )
    row = cur.fetchone()
    return row[0] if row else None


def normalize_payment_rows(
    conn: sqlite3.Connection,
    raw_rows: Union[List[Row], Dict[str, Row]],
    *,
    sessions_source: Union[List[Row], Dict[str, Row], None] = None,
    debug: bool = False
) -> Tuple[List[Row], int]:  # <- return (rows, fk_invalid_count)
    lod = to_list_of_dicts(raw_rows)

    need_usernames = {r.get("initiator") for r in lod if r.get("initiator")}
    initiator_map = _map_usernames_to_user_ids(
        conn, {u for u in need_usernames if u})

    json_session_map: Dict[int, Tuple[Any, Any, Any, Any]] = {}
    if sessions_source is not None:
        json_session_map = _build_session_natural_key_map(sessions_source)

    out: List[Row] = []
    fk_invalid = 0

    for r in lod:
        t_data = r.get("t_data") or {}
        transaction_id = r.get("transaction_id") or r.get("transaction")
        amount = r.get("amount", t_data.get("amount"))

        uid_from_json = _to_int(r.get("user_id"))
        uid_from_initiator = initiator_map.get(
            str(r["initiator"])) if r.get("initiator") else None
        user_id = uid_from_initiator or uid_from_json

        session_id = _to_int(r.get("session_id"))
        if session_id is not None and not _db_has_session_id(conn, session_id):
            if sessions_source is not None and session_id in json_session_map:
                key = json_session_map[session_id]
                new_sid = _db_find_session_id_by_key(conn, key)
                if new_sid is not None:
                    session_id = new_sid

        parking_lot_id = _to_int(r.get("parking_lot_id"))

        norm = {
            "transaction_id": transaction_id,
            "amount":         _to_float(amount),
            "user_id":        _to_int(user_id) if user_id is not None else None,
            "session_id":     session_id,
            "parking_lot_id": parking_lot_id,
            "created_at":     _parse_dt_lenient(r.get("created_at")) or r.get("created_at"),
            "completed":      _coerce_completed(r.get("completed")),
            "hash":           r.get("hash"),
            "t_date":         _parse_dt_lenient(t_data.get("date")) or t_data.get("date"),
            "t_method":       t_data.get("method"),
            "t_issuer":       t_data.get("issuer"),
            "t_bank":         t_data.get("bank"),
        }

        # FK sanity
        fk_missing = []
        if norm["user_id"] is None or not _db_has_user_id(conn, norm["user_id"]):
            fk_missing.append("user_id")
        if norm["session_id"] is None or not _db_has_session_id(conn, norm["session_id"]):
            fk_missing.append("session_id")
        if norm["parking_lot_id"] is None or not _db_has_parking_lot_id(conn, norm["parking_lot_id"]):
            fk_missing.append("parking_lot_id")

        if fk_missing:
            fk_invalid += 1
            if debug:
                print(
                    f"[PAY-FK] skipping tx={transaction_id} missing/invalid FKs: {fk_missing}")
            continue

        out.append(norm)

    return out, fk_invalid


def insert_payments(
    conn: sqlite3.Connection,
    rows: Union[List[Row], Dict[str, Row]],
    *,
    sessions_source: Union[List[Row], Dict[str, Row], None] = None,
    debug: bool = False
) -> Dict[str, int]:
    # Ensure uniqueness so duplicates become "skipped"
    ensure_unique_index_payments(conn)

    rows_norm, fk_invalid = normalize_payment_rows(
        conn, rows, sessions_source=sessions_source, debug=debug)

    # Count rows that miss required columns (incl. NULL tx_id, etc.) as failed
    rows_ok, missing = _require_fields(rows_norm, PAY_FIELDS, debug=debug)
    data = _normalize_rows(rows_ok, PAY_FIELDS)

    result = _batch_insert_per_row(
        conn, SQL_INSERT_PAYMENTS_IGNORE, data, debug=debug)

    # Add in our pre-insert failures
    result["failed"] += (missing + fk_invalid)
    return result


# ------------------- RESERVATIONS (with email remap) ----------------------


# NB: 'id' is deel van RES_FIELDS en wordt gevuld uit de JSON
RES_FIELDS = ("id", "user_id", "parking_lot_id", "vehicle_id",
              "start_time", "duration", "status", "created_at")

SQL_INSERT_RES = f"""
INSERT OR IGNORE INTO reservations ({", ".join(RES_FIELDS)})
VALUES ({", ".join("?" for _ in RES_FIELDS)});
"""


def _pick_duration(r: Row) -> Union[int, None]:
    for key in ("duration", "duration_minutes", "durationMinutes"):
        d = _to_int(r.get(key))
        if d is not None:
            return d
    start_keys = ("start_time", "startTime", "start",
                  "start_datetime", "startDateTime")
    end_keys = ("end_time",   "endTime",   "end",
                "end_datetime",   "endDateTime")
    start = next((r.get(k) for k in start_keys if r.get(k)), None)
    end = next((r.get(k) for k in end_keys if r.get(k)), None)
    if start and end:
        return calculate_duration(start, end)
    return None


def normalize_reservation_rows(raw_rows, *, debug: bool = False) -> List[Row]:
    lod = to_list_of_dicts(raw_rows)
    out: List[Row] = []
    shown = 0
    for r in lod:
        dur = _pick_duration(r)
        norm = {
            "id":            _to_int(r.get("id")),
            "user_id":        _to_int(r.get("user_id")),
            "parking_lot_id": _to_int(r.get("parking_lot_id")),
            "vehicle_id":     _to_int(r.get("vehicle_id")),
            "start_time":     r.get("start_time") or r.get("startTime") or r.get("start") or r.get("start_datetime") or r.get("startDateTime"),
            "duration":       _to_int(dur),
            "status":         r.get("status"),
            "created_at":     r.get("created_at") or r.get("createdAt"),
        }
        if debug and (norm["duration"] is None) and shown < 10:
            present = [k for k in r.keys() if r.get(k) is not None]
            print(
                f"[RESERVE] no duration for id={r.get('id')} present_keys={present}")
            shown += 1
        out.append(norm)
    return out


def remap_reservation_user_ids_by_email(
    conn: sqlite3.Connection,
    reservations_rows: List[Row],
    users_source: Union[List[Row], Dict[str, Row]],
    *,
    debug: bool = False
) -> Tuple[List[Row], int]:
    id_to_email = extract_userid_to_email(users_source)
    emails: Set[str] = set()

    for r in reservations_rows:
        json_uid = _to_int(r.get("user_id"))
        if json_uid is None:
            continue
        email = id_to_email.get(json_uid)
        if email:
            emails.add(email)

    email_to_dbid = map_emails_to_db_user_ids(conn, emails)

    unresolved = 0
    for r in reservations_rows:
        json_uid = _to_int(r.get("user_id"))
        if json_uid is None:
            continue
        email = id_to_email.get(json_uid)
        if not email:
            unresolved += 1
            if debug:
                print(f"[REMAP] no email for json_user_id={json_uid}")
            continue
        db_uid = email_to_dbid.get(email)
        if db_uid is not None:
            r["user_id"] = db_uid
        else:
            unresolved += 1
            if debug:
                print(f"[REMAP] email '{email}' not found in DB users")

    return reservations_rows, unresolved


def insert_reservations(
    conn: sqlite3.Connection,
    rows,
    *,
    users_source: Union[List[Row], Dict[str, Row], None] = None,
    debug: bool = False
) -> Dict[str, int]:
    rows_norm = normalize_reservation_rows(rows, debug=debug)

    unresolved = 0
    if users_source is not None:
        rows_norm, unresolved = remap_reservation_user_ids_by_email(
            conn, rows_norm, users_source, debug=debug
        )

    rows_ok, missing = _require_fields(rows_norm, RES_FIELDS, debug=debug)
    data = _normalize_rows(rows_ok, RES_FIELDS)
    result = _batch_insert_per_row(conn, SQL_INSERT_RES, data, debug=debug)
    result["failed"] += (missing + unresolved)
    return result


# ------------------- PARKING SESSIONS (with alias resolvers) ----------------

# ---- SESSIONS: kolomvolgorde afgestemd op je DB ----
SESS_FIELDS = (
    "parking_lot_id",      # 1
    "vehicle_id",          # 2
    "user_id",             # 3
    "started",             # 4
    "duration_minutes",    # 5
    "payment_status"       # 6
)

SQL_INSERT_SESSIONS_IGNORE = f"""
INSERT OR IGNORE INTO sessions ({", ".join(SESS_FIELDS)})
VALUES ({", ".join("?" for _ in SESS_FIELDS)});
"""

SQL_INSERT_SESSIONS_IGNORE = f"""
INSERT OR IGNORE INTO sessions ({", ".join(SESS_FIELDS)})
VALUES ({", ".join("?" for _ in SESS_FIELDS)});
"""


def ensure_unique_index_sessions(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_sessions_natural
        ON sessions (user_id, parking_lot_id, vehicle_id, started);
    """)
    conn.commit()


def _map_usernames_to_user_ids(conn: sqlite3.Connection, usernames: Set[str]) -> Dict[str, int]:
    if not usernames:
        return {}
    cur = conn.cursor()
    cur.execute(
        f"SELECT username, id FROM users WHERE username IN {_make_in_clause(len(usernames))}",
        tuple(usernames)
    )
    return {row[0]: row[1] for row in cur.fetchall()}


def _map_plates_to_vehicle_ids(conn: sqlite3.Connection, plates: Set[str]) -> Dict[str, int]:
    if not plates:
        return {}
    cur = conn.cursor()
    cur.execute(
        f"SELECT license_plate, id FROM vehicles WHERE license_plate IN {_make_in_clause(len(plates))}",
        tuple(plates)
    )
    return {row[0]: row[1] for row in cur.fetchall()}


def _parse_started_lenient(s: Any) -> str | None:
    if not s:
        return None
    txt = str(s).strip()
    from datetime import datetime
    # Z → +00:00 voor %z
    if txt.endswith("Z"):
        try:
            dt = datetime.strptime(txt.replace(
                "Z", "+00:00"), "%Y-%m-%dT%H:%M:%S%z")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    patterns = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    for p in patterns:
        try:
            dt = datetime.strptime(txt, p)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    return None


def _minutes_between_lenient(start_iso: Any, end_iso: Any) -> Union[int, None]:
    # gebruikt jouw bestaande calculate_duration als fallback
    s = str(start_iso) if start_iso is not None else None
    e = str(end_iso) if end_iso is not None else None
    if not s or not e:
        return None
    # probeer robuuste parser
    try:
        from datetime import datetime, timezone
        fmt_s = s.replace("Z", "+00:00")
        fmt_e = e.replace("Z", "+00:00")
        # probeer met %z
        for p in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
            try:
                ds = datetime.strptime(fmt_s, p)
                de = datetime.strptime(fmt_e, p)
                return int((de - ds).total_seconds() // 60)
            except Exception:
                continue
    except Exception:
        pass
    # fallback naar jouw helper
    try:
        return calculate_duration(s, e)
    except Exception:
        return None


def _normalize_parking_session_rows(
    conn: sqlite3.Connection,
    raw_rows: Union[List[Row], Dict[str, Row]],
    *,
    debug: bool = False
) -> List[Row]:
    """
    Ondersteunt aliassen:
      - user_id  | username | user
      - vehicle_id | license_plate | licenseplate
      - started | start_time | start | startDateTime
      - stopped (alleen voor duur-berekening)
      - duration_minutes | duration | durationMinutes
      - payment_status | paymentStatus | status
    """
    lod = to_list_of_dicts(raw_rows)

    # Bulk resolvers (inclusief aliassen)
    usernames = {
        (r.get("username") or r.get("user"))
        for r in lod if (r.get("username") or r.get("user"))
    }
    plates = {
        (r.get("license_plate") or r.get("licenseplate"))
        for r in lod if (r.get("license_plate") or r.get("licenseplate"))
    }
    user_map = _map_usernames_to_user_ids(conn, {u for u in usernames if u})
    plate_map = _map_plates_to_vehicle_ids(conn, {p for p in plates if p})

    out: List[Row] = []
    for r in lod:
        # user_id: prefer alias username/user mapping
        uname = r.get("username") or r.get("user")
        uid = user_map.get(uname) if uname else _to_int(r.get("user_id"))

        # vehicle_id: prefer licenseplate alias mapping
        plate = r.get("license_plate") or r.get("licenseplate")
        vid = plate_map.get(plate) if plate else _to_int(r.get("vehicle_id"))

        # started (alias)
        started_raw = r.get("started") or r.get(
            "start_time") or r.get("start") or r.get("startDateTime")
        started = _parse_started_lenient(started_raw)

        # duration (alias) → int; zo niet, bereken via stopped
        dur = r.get("duration_minutes") or r.get(
            "duration") or r.get("durationMinutes")
        dur = _to_int(dur)
        if dur is None:
            stopped = r.get("stopped") or r.get("stop_time") or r.get(
                "end_time") or r.get("end") or r.get("endDateTime")
            dur = _minutes_between_lenient(started_raw, stopped)

        # status (alias)
        status = r.get("payment_status") or r.get(
            "paymentStatus") or r.get("status") or "unknown"

        norm = {
            "parking_lot_id": _to_int(r.get("parking_lot_id")),
            "vehicle_id":     _to_int(vid),
            "user_id":        _to_int(uid),
            "started":        started,
            "duration_minutes": _to_int(dur),
            "payment_status": status,
        }

        if debug:
            missing = [k for k in SESS_FIELDS if norm.get(k) is None]
            if missing:
                print(
                    f"[SESS-NORM] missing fields -> {missing} | aliases used: user='{uname}', plate='{plate}' | raw keys: {list(r.keys())}")

        out.append(norm)
    return out


def _db_has_fk(conn: sqlite3.Connection, table: str, col: str, val: int) -> bool:
    cur = conn.cursor()
    cur.execute(f"SELECT 1 FROM {table} WHERE {col}=? LIMIT 1;", (val,))
    return cur.fetchone() is not None


def insert_parking_sessions(
    conn: sqlite3.Connection,
    rows: Union[List[Row], Dict[str, Row]],
    *,
    debug: bool = False
) -> Dict[str, int]:
    """
    Insert parking sessions, FK-safe en idempotent.
    - user_id via alias 'user'/'username'
    - vehicle_id via alias 'licenseplate'/'license_plate'
    - duration berekend uit started/stopped als nodig
    - duplicates voorkomen via UNIQUE index + INSERT OR IGNORE
    """
    ensure_unique_index_sessions(conn)

    rows_norm = _normalize_parking_session_rows(conn, rows, debug=debug)
    print(rows_norm[:3])

    # Prefilter: skip rijen met missende/verkeerde FKs om FOREIGN KEY errors te vermijden
    valid_rows: List[Row] = []
    skipped_fk = 0
    for r in rows_norm:
        if None in (r["user_id"], r["vehicle_id"], r["parking_lot_id"], r["started"], r["duration_minutes"]):
            skipped_fk += 1
            if debug:
                print(f"[SESS-FK] skip (None field) -> {r}")
            continue
        if not _db_has_fk(conn, "users", "id", r["user_id"]):
            skipped_fk += 1
            if debug:
                print(f"[SESS-FK] user_id not found: {r['user_id']}")
            continue
        if not _db_has_fk(conn, "vehicles", "id", r["vehicle_id"]):
            skipped_fk += 1
            if debug:
                print(f"[SESS-FK] vehicle_id not found: {r['vehicle_id']}")
            continue
        if not _db_has_fk(conn, "parking_lots", "id", r["parking_lot_id"]):
            skipped_fk += 1
            if debug:
                print(
                    f"[SESS-FK] parking_lot_id not found: {r['parking_lot_id']}")
            continue
        valid_rows.append(r)

    rows_ok, missing = _require_fields(valid_rows, SESS_FIELDS, debug=debug)
    data = _normalize_rows(rows_ok, SESS_FIELDS)

    result = _batch_insert_per_row(
        conn, SQL_INSERT_SESSIONS_IGNORE, data, debug=debug)
    # tel prefilter-skips mee als 'failed'
    result["failed"] = result.get("failed", 0) + missing + skipped_fk
    return result

# ------------------- Wipe table ----------------------------


def wipe_table(conn: sqlite3.Connection, table_name: str, *, reset_autoincrement: bool = True):
    """
    Verwijdert alle records uit een tabel.
    Als reset_autoincrement=True wordt ook de AUTOINCREMENT teller gereset.
    """
    cur = conn.cursor()
    if not re.match(r'^[A-Za-z0-9_]+$', table_name):
        raise ValueError(f"Ongeldige tabelnaam: {table_name}")

    cur.execute(f"DELETE FROM {table_name};")
    if reset_autoincrement:
        cur.execute("DELETE FROM sqlite_sequence WHERE name=?;", (table_name,))
    conn.commit()
    print(f"Tabel '{table_name}' gewist.")

# -------------------------- __all__ ------------------------


__all__ = [
    # inserts
    "insert_users",
    "insert_parking_lots",
    "insert_vehicles",
    "insert_payments",
    "insert_reservations",
    # helpers
    "calculate_duration",
    "extract_userid_to_email",
    "map_emails_to_db_user_ids",
    "remap_reservation_user_ids_by_email",
    "wipe_table",
]

conn = get_connection()

# parking_lots = load_data("v1/data/parking-lots.json")
# print("lots:", insert_parking_lots(conn, parking_lots, debug=True))

# users = load_data("v1/data/users.json")
# print("users:", insert_users(conn, users, debug=True))

# vehicles = load_data("v1/data/vehicles.json")
# print("vehicles:", insert_vehicles(conn, vehicles, debug=True))

# reservations = load_data("v1/data/reservations.json")
# print("reservations:", insert_reservations(
#     conn, reservations, users_source=users, debug=True))

parking_sessions = load_data("v1/data/pdata/p1-sessions.json")
print("sessions:", insert_parking_sessions(
    conn, parking_sessions, debug=False))

payments = load_data("v1/data/payments2.json")
print("payments:", insert_payments(conn, payments, debug=True))
