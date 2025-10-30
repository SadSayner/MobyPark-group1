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

USER_ALIAS_TEMP_CSV = "v1/Database/usernames_temp.csv"


def merge_dicts_numbered(a: dict, b: dict) -> dict:
    """
    Merge b into a. Keys zijn (bij voorkeur) numerieke strings of ints.
    - Als key uit b vrij is -> direct plaatsen.
    - Bij overlap -> geef volgende vrije numerieke key (max+1, max+2, ...)
    Werkt O(n+m) i.p.v. O(n*m).
    """
    result = dict(a)

    # Verzamel bestaande numerieke keys (string "123" of int 123)
    used_nums = set()
    for k in result.keys():
        try:
            used_nums.add(int(k))
        except (ValueError, TypeError):
            # Niet-numerieke sleutel in a negeren voor nummering
            pass

    next_num = (max(used_nums) + 1) if used_nums else 1

    def take_next_free():
        nonlocal next_num
        # Sla door tot we een ongebruikt nummer hebben
        while str(next_num) in result or next_num in result:
            next_num += 1
        key = str(next_num)
        used_nums.add(next_num)
        next_num += 1
        return key

    for k, v in b.items():
        # Probeer directe plaatsing als key nog niet bestaat
        if k not in result:
            result[k] = v
            # Als het een numerieke key is, update next_num indien nodig
            try:
                kn = int(k)
                if kn >= next_num:
                    next_num = kn + 1
                used_nums.add(kn)
            except (ValueError, TypeError):
                pass
            continue

        # Conflict: geef een nieuw numeriek sleutel
        new_k = take_next_free()
        result[new_k] = v

    return result


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
# ------------------- CSV Helpers ---------------------------


def read_user_alias_csv(csv_path: str = USER_ALIAS_TEMP_CSV) -> Dict[str, str]:
    """
    Reads usernames_temp.csv and returns:
      lower(alias_username) -> lower(canonical_username)

    Blank canonical_username rows are ignored (still unresolved = manual fix needed)
    """
    alias_map: Dict[str, str] = {}

    if not os.path.exists(csv_path):
        return alias_map  # no file -> no aliases

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            alias = (row.get("alias_username") or "").strip().lower()
            canon = (row.get("canonical_username") or "").strip().lower()
            if alias and canon:
                alias_map[alias] = canon

    return alias_map


def _to_list_of_dicts(obj) -> List[dict]:
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        return list(obj.values())
    return []


def build_aliases_from_user_json(
    users_json_path: str,
    out_csv_path: str = "usernames_temp.csv",
) -> Dict[str, int]:
    """
    Reads users.json only.
    Groups by email.
    First record for each email is canonical.
    Any additional usernames for the same email
      -> listed as aliases needing mapping.
    """
    raw = load_json(users_json_path)
    users = _to_list_of_dicts(raw)

    seen_email: Dict[str, str] = {}  # lower(email) -> canonical username
    alias_rows: List[Tuple[str, str, str]] = []

    for u in users:
        uname = (u.get("username") or "").strip()
        email = (u.get("email") or "").strip()

        if not uname or not email:
            continue

        email_l = email.lower()
        uname_l = uname.lower()

        if email_l not in seen_email:
            # First user for this email → canonical
            seen_email[email_l] = uname
        else:
            # Duplicate email → this username becomes an alias
            canonical_uname = seen_email[email_l]
            alias_rows.append((uname, canonical_uname, "duplicate email"))

    # Avoid overwriting folder errors
    os.makedirs(os.path.dirname(out_csv_path) or ".", exist_ok=True)

    with open(out_csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["alias_username", "canonical_username", "note"])
        alias_rows_sorted = sorted(alias_rows, key=lambda r: r[0].lower())
        w.writerows(alias_rows_sorted)

    return {
        "emails": len(seen_email),
        "aliases_written": len(alias_rows),
        "csv_path": out_csv_path,
    }


def delete_user_alias_csv(csv_path: str = USER_ALIAS_TEMP_CSV) -> bool:
    """
    Deletes the temp CSV. Returns True if deleted, False if it didn't exist.
    """
    if os.path.exists(csv_path):
        os.remove(csv_path)
        return True
    return False

# ------------------- USERS ------------------------------


USERS_FIELDS = ("username", "password", "name", "email", "phone",
                "role", "created_at", "birth_year", "active")

SQL_INSERT_USERS_IGNORE = f"""
INSERT OR IGNORE INTO users ({", ".join(USERS_FIELDS)})
VALUES ({", ".join("?" for _ in USERS_FIELDS)});
"""


def insert_users(conn: sqlite3.Connection, rows: Union[List[Row], Dict[str, Row]], *, debug: bool = False) -> Dict[str, int]:
    build_aliases_from_user_json(
        "v1/data/users.json", USER_ALIAS_TEMP_CSV)
    """
    Verwacht alle NOT NULL velden. Vult default role='USER' als niet gegeven.
    Email is UNIQUE in DB -> duplicates worden 'skipped' via OR IGNORE.
    Maakt of update een tijdelijke alias CSV voor latere sessie-import fase.
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
        conn, SQL_INSERT_USERS_IGNORE, data, debug=debug
    )
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


# ------------------- SESSIONS ------------------------------

SESSIONS_FIELDS = (
    "parking_lot_id",
    "user_id",
    "started",
    "duration_minutes",
    "payment_status",
)

SQL_INSERT_SESSIONS_IGNORE = f"""
INSERT OR IGNORE INTO sessions ({", ".join(SESSIONS_FIELDS)})
VALUES ({", ".join("?" for _ in SESSIONS_FIELDS)});
"""


def ensure_unique_index_sessions(conn: sqlite3.Connection):
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_sessions_unique
        ON sessions (user_id, parking_lot_id, started);
    """)
    conn.commit()


def _lenient_parse_dt(value):
    """
    Parse ISO-like strings (supports trailing 'Z') into a timezone-aware UTC datetime.
    - If value is already a datetime, normalize to UTC.
    - Naive datetimes are assumed to be UTC.
    """
    if value is None:
        return None

    # Already a datetime?
    if isinstance(value, datetime.datetime):
        return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)

    # Convert to string safely
    s = str(value).strip()
    if not s:
        return None

    # Support 'Z' suffix by converting it to '+00:00'
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    try:
        dt = datetime.datetime.fromisoformat(s)
    except Exception:
        # Fallback: tolerate a space between date/time and an unhandled trailing Z
        s2 = s.replace(" ", "T")
        if s2.endswith("Z"):
            s2 = s2[:-1] + "+00:00"
        dt = datetime.datetime.fromisoformat(s2)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    return dt.astimezone(datetime.timezone.utc)


def _iso_utc(dtobj):
    """
    Return an ISO 8601 UTC string with 'Z' suffix (e.g. '2021-03-25T20:45:37Z').
    """
    if dtobj is None:
        return None
    return (
        dtobj.astimezone(datetime.timezone.utc)
        .replace(tzinfo=datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _map_usernames_to_user_ids(conn, usernames: Set[str]) -> Dict[str, int]:
    """
    Case-insensitive mapping of username -> user_id from the users table.
    Keys in the returned dict are LOWERCASE usernames.
    """
    cleaned = sorted({(u or "").strip().lower()
                     for u in usernames if (u or "").strip()})
    if not cleaned:
        return {}

    placeholders = ",".join("?" for _ in cleaned)
    sql = f"SELECT id, username FROM users WHERE LOWER(username) IN ({placeholders})"
    cur = conn.execute(sql, cleaned)

    out: Dict[str, int] = {}
    for row in cur.fetchall():
        uid, uname = row[0], row[1]
        if uname:
            out[str(uname).strip().lower()] = int(uid)
    return out


def _first(*vals):
    """Return the first non-empty value (treat '' as empty)."""
    for v in vals:
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        return v
    return None


def insert_parking_sessions(conn, rows: Union[List[dict], Dict[str, dict]], *, debug: bool = False) -> Dict[str, int]:
    """
    Batch insert parking sessions.

    Resolution order for user_id:
      1) DB lookup by username (case-insensitive)
      2) CSV alias fallback: alias_username -> canonical_username, then DB lookup

    Any user_id coming from JSON is ignored — DB autoincrements session_id.
    """
    ensure_unique_index_sessions(conn)
    lod: List[dict] = to_list_of_dicts(rows)

    # -------- Load CSV alias map ----------
    try:
        alias_map: Dict[str, str] = read_user_alias_csv()
    except Exception:
        alias_map = {}

    # -------- Gather session usernames ----------
    session_usernames: Set[str] = set()
    for r in lod:
        uname = _first(r.get("username"), r.get("user"), r.get("user_name"))
        if isinstance(uname, str) and uname.strip():
            session_usernames.add(uname.strip())

    # 1st pass: resolve username directly from DB
    username_map = _map_usernames_to_user_ids(conn, session_usernames)

    # For unresolved ones: check CSV alias
    unresolved = {u for u in session_usernames if u.lower()
                  not in username_map}
    canonical_usernames_needed = {
        alias_map.get(u.lower()) for u in unresolved if alias_map.get(u.lower())
    }
    canonical_usernames_needed.discard(None)

    canonical_map = {}
    if canonical_usernames_needed:
        canonical_map = _map_usernames_to_user_ids(
            conn, canonical_usernames_needed)

    # -------- Prepare rows ----------
    prepared: List[dict] = []
    failed_missing = 0

    for r in lod:
        uname = _first(r.get("username"), r.get("user"), r.get("user_name"))
        uid = None

        if isinstance(uname, str) and uname.strip():
            uname_l = uname.strip().lower()
            uid = username_map.get(uname_l)
            if uid is None:
                canon_l = alias_map.get(uname_l)
                if canon_l:
                    uid = canonical_map.get(canon_l)

        # Parse datetime
        started_raw = _first(
            r.get("started"), r.get("start"), r.get(
                "start_time"), r.get("startDateTime")
        )
        started_dt = _lenient_parse_dt(started_raw)
        started_iso = _iso_utc(started_dt) if started_dt else None

        # Duration
        dur_raw = _first(r.get("duration_minutes"),
                         r.get("duration"), r.get("minutes"))
        duration_minutes = _to_int(dur_raw)

        if duration_minutes is None:
            stopped_raw = _first(r.get("stopped"), r.get(
                "stop"), r.get("end"), r.get("end_time"))
            stopped_dt = _lenient_parse_dt(stopped_raw)
            if started_dt and stopped_dt:
                duration_minutes = max(
                    0, int((stopped_dt - started_dt).total_seconds() / 60.0))

        payment_status = _first(r.get("payment_status"), r.get(
            "paymentStatus"), r.get("status"))
        parking_lot_id = _to_int(
            _first(r.get("parking_lot_id"), r.get("lot_id"),
                   r.get("parkingLotId"), r.get("parking_lot"))
        )

        # Validation
        if None in (uid, parking_lot_id, started_iso, duration_minutes, payment_status):
            failed_missing += 1
            if debug:
                print(f"[insert_sessions] missing fields for row: {r}")
            continue

        prepared.append({
            "parking_lot_id": parking_lot_id,
            "user_id": uid,                    # ✅ user_id determined by DB/CSV
            "started": started_iso,            # ✅ session_id autoincrement happens automatically
            "duration_minutes": int(duration_minutes),
            "payment_status": str(payment_status),
        })

    data = _normalize_rows(prepared, SESSIONS_FIELDS)
    result = _batch_insert_per_row(
        conn, SQL_INSERT_SESSIONS_IGNORE, data, debug=debug)
    result["failed"] += failed_missing
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

wipe_table(conn, "sessions")

all_sessions = []

for i in range(1, 1501):
    file_path = f"v1/data/pdata/p{i}-sessions.json"
    try:
        data = load_data(file_path)
        # Voeg ALLE values toe, dict -> list
        all_sessions.extend(data.values())
    except FileNotFoundError:
        # Veilig overslaan als een bestand ontbreekt
        pass

batch_size = 200000
for start in range(0, len(all_sessions), batch_size):
    batch = all_sessions[start:start + batch_size]
    result = insert_parking_sessions(conn, batch, debug=True)
    print(
        f"In batch {start // batch_size + 1}: inserted={result['inserted']}, failed={result['failed']}")

    # delete_user_alias_csv()

    # payments = load_data("v1/data/payments2.json")
    # print("payments:", insert_payments(conn, payments, debug=True))
