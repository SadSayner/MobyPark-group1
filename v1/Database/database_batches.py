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
from ..storage_utils import *  # noqa
from .database_creation import create_database  # noqa

Row = Dict[str, Any]
Rows = Iterable[Row]

# -------------------------- Utilities --------------------------

USER_ALIAS_TEMP_CSV = "v1/Database/usernames_temp.csv"


def to_list_of_dicts(data: Union[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [v for v in data.values() if isinstance(v, dict)]
    raise TypeError("Expected list[dict] or dict[str, dict]")


def _to_int_bool(v: Any) -> Any:
    return int(v) if isinstance(v, bool) else v


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
PAY_FIELDS: Tuple[str, ...] = (
    "transaction_id", "amount", "user_id", "session_id", "parking_lot_id",
    "created_at", "completed", "hash", "t_date", "t_method", "t_issuer", "t_bank"
)

SQL_INSERT_PAYMENTS_IGNORE = f"""
INSERT OR IGNORE INTO payments ({", ".join(PAY_FIELDS)})
VALUES ({", ".join("?" for _ in PAY_FIELDS)});
"""

# -- Kleine utilities ---------------------------------------------------------


def _to_int(x: Any) -> Union[int, None]:
    try:
        if x is None or x == "":
            return None
        return int(float(x))
    except Exception:
        return None


def _to_float(x: Any) -> Union[float, None]:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except Exception:
        return None


def _normalize_completed(x: Any) -> int:
    # heel simpel: truthy -> 1, anders 0
    if isinstance(x, bool):
        return 1 if x else 0
    if isinstance(x, (int, float)):
        return 0 if float(x) == 0.0 else 1
    if x is None:
        return 0
    s = str(x).strip().lower()
    return 1 if s in {"1", "true", "t", "yes", "y", "done", "completed"} else 0


def _to_list_of_dicts(rows: Union[List[Row], Dict[str, Row]]) -> List[Row]:
    if isinstance(rows, dict):
        return list(rows.values())
    return list(rows or [])


# -- Aliassen laden en username-resolving ------------------------------------


def load_alias_map_from_csv(path: str) -> Dict[str, str]:
    """
    Verwacht CSV met kolommen: alias_username, canonical_username, ...
    Geeft dict: lower(alias) -> canonical_username (zoals in DB 'users.username').
    """
    mapping: Dict[str, str] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            alias = (row.get("alias_username") or "").strip()
            canon = (row.get("canonical_username") or "").strip()
            if alias and canon:
                mapping[alias.lower()] = canon
    return mapping


def _map_usernames_to_user_ids(conn: sqlite3.Connection, usernames: Set[str]) -> Dict[str, int]:
    if not usernames:
        return {}
    # let op: IN (...) parameters
    qmarks = ",".join("?" for _ in usernames)
    sql = f"SELECT username, id FROM users WHERE username IN ({qmarks})"
    cur = conn.cursor()
    cur.execute(sql, tuple(usernames))
    return {row[0].lower(): int(row[1]) for row in cur.fetchall()}


# -- Uniek index + (optioneel) cleanup ---------------------------------------


def ensure_unique_index_payments(conn: sqlite3.Connection) -> None:
    """
    Zorg voor unieke transaction_id. Als er nog dubbele rijen bestaan,
    verwijder we alles behalve de oudste en maken dan de index aan.
    """
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_payments_tx
            ON payments (transaction_id);
        """)
        conn.commit()
    except sqlite3.IntegrityError:
        # bestaande duplicaten opruimen en opnieuw proberen
        cur.execute("""
            DELETE FROM payments
            WHERE rowid NOT IN (
                SELECT MIN(rowid) FROM payments GROUP BY transaction_id
            );
        """)
        conn.commit()
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_payments_tx
            ON payments (transaction_id);
        """)
        conn.commit()

# -- Kern: normaliseren + batch insert ---------------------------------------


def normalize_payment_rows_simple(
    raw_rows: Union[List[Row], Dict[str, Row]],
    *,
    username_to_id: Dict[str, int],
) -> Tuple[List[Row], int]:
    """
    Minimalistische normalisatie:
    - kiest velden uit PAY_FIELDS
    - user_id uit row of via username/user/user_name + alias-resolve
    - completed eenvoudig naar 0/1
    - géén zware datum parsing: strings gaan zoals ze zijn
    Retourneert (rows_ok, missing_count)
    """
    lod = _to_list_of_dicts(raw_rows)
    out: List[Row] = []
    missing = 0

    for r in lod:
        # 1) transaction_id & amount
        tx = _first(r.get("transaction_id"), r.get("transaction"))
        amount = _first(r.get("amount"), (r.get("t_data") or {}).get("amount"))

        # 2) user_id
        user_id = _to_int(_first(r.get("user_id")))
        if user_id is None:
            uname = _first(r.get("username"), r.get(
                "user"), r.get("user_name"))
            if isinstance(uname, str) and uname.strip():
                user_id = username_to_id.get(uname.strip().lower())

        # 3) sessie / parking lot
        session_id = _to_int(r.get("session_id"))
        parking_lot_id = _to_int(r.get("parking_lot_id"))

        # 4) overige
        t_data = r.get("t_data") or {}
        norm = {
            "transaction_id": tx,
            "amount":         _to_float(amount),
            "user_id":        user_id,
            "session_id":     session_id,
            "parking_lot_id": parking_lot_id,
            # string laten zoals is
            "created_at":     _first(r.get("created_at")),
            "completed":      _normalize_completed(r.get("completed")),
            "hash":           r.get("hash"),
            "t_date":         _first(t_data.get("date")),   # idem
            "t_method":       t_data.get("method"),
            "t_issuer":       t_data.get("issuer"),
            "t_bank":         t_data.get("bank"),
        }

        # 5) minimale verplichting
        required = ("transaction_id", "amount", "user_id",
                    "session_id", "parking_lot_id")
        if any(norm[k] in (None, "") for k in required):
            missing += 1
            continue

        out.append(norm)

    return out, missing


def _coerce_completed(val: Any) -> int:
    """
    Normalize various boolean-ish values into 0/1 for 'completed'.
    """
    if isinstance(val, bool):
        return 1 if val else 0
    if isinstance(val, (int, float)):
        return 0 if float(val) == 0.0 else 1
    if val is None:
        return 0

    s = str(val).strip().lower()
    if s in {"true", "t", "yes", "y", "completed", "done", "1"}:
        return 1
    if s in {"false", "f", "no", "n", "0"}:
        return 0

    # fallback: anything else counts as completed
    return 1


def insert_payments(
    conn: sqlite3.Connection,
    rows: Union[List[Row], Dict[str, Row]],
    *,
    debug: bool = False
) -> Dict[str, int]:
    """
    Minimalistische importer in dezelfde stijl als insert_users:
    - transaction <- transaction_id (alias)
    - user_id uit 'initiator' (fallback: username/user/user_name), met alias_map → canonical
    - completed naar 0/1
    - t_data flatten (date/method/issuer/bank)
    - UNIQUE op transaction_id via OR IGNORE + vooraf aangemaakte UNIQUE index.
    """
    ensure_unique_index_payments(conn)

    lod = to_list_of_dicts(rows)

    # ---- 1) verzamel alle relevante usernames (case-insensitive)
    usernames: Set[str] = set()
    for r in lod:
        uname = _first(r.get("initiator"), r.get("username"),
                       r.get("user"), r.get("user_name"))
        if isinstance(uname, str) and uname.strip():
            usernames.add(uname.strip().lower())

    # 1a) directe DB-lookup (let op: helper geeft keys al lowercase terug)
    direct_map = _map_usernames_to_user_ids(
        conn, usernames)  # { lower(username): id }

    # 1b) alias → canonical (beide lowercase) → DB-lookup
    try:
        alias_map: Dict[str, str] = read_user_alias_csv()
    except Exception:
        print(
            "[insert_sessions] failed to read username alias CSV, proceeding without aliases")
        alias_map = {}
    canonical_needed: Set[str] = set()
    for u_lc in usernames:
        if u_lc not in direct_map:
            canon = alias_map.get(u_lc)  # verwacht lowercase keys/values
            if isinstance(canon, str) and canon.strip():
                canonical_needed.add(canon.strip().lower())

    canonical_map = {}
    if canonical_needed:
        canonical_map = _map_usernames_to_user_ids(
            conn, canonical_needed)  # { lower(canonical): id }

    # ---- 2) pre-normalisatie per rij
    for r in lod:
        # (a) transaction alias → transaction_id
        if not r.get("transaction_id") and r.get("transaction"):
            r["transaction_id"] = r.get("transaction")

        # (b) amount uit hoofdveld of t_data.amount
        t_data = r.get("t_data") or {}
        r["amount"] = _to_float(_first(r.get("amount"), t_data.get("amount")))

        # (c) user_id bepalen: initiator > username > user > user_name
        if r.get("user_id") in (None, ""):
            uname = _first(r.get("initiator"), r.get("username"),
                           r.get("user"), r.get("user_name"))
            uid = None
            if isinstance(uname, str) and uname.strip():
                key_lc = uname.strip().lower()
                # 1. direct
                uid = direct_map.get(key_lc)
                # 2. alias → canonical → DB
                if uid is None and alias_map:
                    canon = alias_map.get(key_lc)
                    if isinstance(canon, str) and canon.strip():
                        uid = canonical_map.get(canon.strip().lower())
            r["user_id"] = _to_int(uid)
        else:
            r["user_id"] = _to_int(r.get("user_id"))

        # (d) ids
        r["session_id"] = _to_int(r.get("session_id"))
        r["parking_lot_id"] = _to_int(r.get("parking_lot_id"))

        # (e) completed → 0/1
        r["completed"] = _coerce_completed(r.get("completed"))

        # (f) t_data flatten (laat created_at zoals aangeleverd)
        if not r.get("t_date"):
            r["t_date"] = t_data.get("date")
        if not r.get("t_method"):
            r["t_method"] = t_data.get("method")
        if not r.get("t_issuer"):
            r["t_issuer"] = t_data.get("issuer")
        if not r.get("t_bank"):
            r["t_bank"] = t_data.get("bank")

    # ---- 3) vereiste velden afdwingen
    PAY_REQUIRED = ("transaction_id", "amount", "user_id",
                    "session_id", "parking_lot_id")
    rows_ok, missing = _require_fields(lod, PAY_REQUIRED, debug=debug)

    # ---- 4) volgorde normaliseren en batch-insert
    data = _normalize_rows(rows_ok, PAY_FIELDS)
    result = _batch_insert_per_row(
        conn, SQL_INSERT_PAYMENTS_IGNORE, data, debug=debug)
    result["failed"] += missing

    # consistentie met andere rapportages
    result["duplicates"] = result.pop("skipped", 0)

    if debug:
        # toon 10 onopgeloste initiators (na alias en direct lookup)
        unresolved = []
        for r in lod:
            if r in rows_ok:
                continue  # deze gingen al door
            uname = _first(r.get("initiator"), r.get("username"),
                           r.get("user"), r.get("user_name"))
            if isinstance(uname, str) and uname.strip():
                key_lc = uname.strip().lower()
                if (key_lc not in direct_map) and (alias_map.get(key_lc, "").strip().lower() not in canonical_map):
                    unresolved.append(uname)
        if unresolved:
            print(
                f"[PAY][DEBUG] unresolved usernames (sample up to 10): {unresolved[:10]}")

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
        print(
            "[insert_sessions] failed to read username alias CSV, proceeding without aliases")
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
            if debug and failed_missing <= 10:
                print(f"[insert_sessions] missing fields for row: {r}")
                print(uid, parking_lot_id, started_iso,
                      duration_minutes, payment_status)
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


def load_parking_sessions(debug=False):
    all_sessions = []

    start_time = datetime.datetime.now()

    for i in range(1, 1501):
        file_path = f"v1/data/pdata/p{i}-sessions.json"
        try:
            data = load_data(file_path)
            all_sessions.extend(data.values())
        except FileNotFoundError:
            pass

    if debug:
        print(
            f"Loaded total {len(all_sessions)} sessions in {(datetime.datetime.now() - start_time).total_seconds():.2f} seconds.")
    return all_sessions


def make_batches(all_info, batch_size: int = 400000, debug: bool = False):
    all_items = to_list_of_dicts(all_info)
    for start in range(0, len(all_items), batch_size):
        yield all_items[start:start + batch_size]


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


def fill_database():
    if not os.path.exists('v1/Database/MobyPark.db'):
        print(f"Database 'v1/Database/MobyPark.db' bestaat niet.")
        create_database('v1/Database/MobyPark.db')

    conn = get_connection()

    parking_lots = load_data("v1/data/parking-lots.json")
    print("lots:", insert_parking_lots(conn, parking_lots, debug=True))

    users = load_data("v1/data/users.json")
    print("users:", insert_users(conn, users, debug=True))

    vehicles = load_data("v1/data/vehicles.json")
    print("vehicles:", insert_vehicles(conn, vehicles, debug=True))

    reservations = load_data("v1/data/reservations.json")
    print("reservations:", insert_reservations(
        conn, reservations, users_source=users, debug=True))

    all_sessions = load_parking_sessions(True)
    batches = make_batches(all_sessions, 400000, debug=True)
    for batch in batches:
        result = insert_parking_sessions(conn, batch, debug=True)
        print(
            f"In batch: inserted={result['inserted']}, failed={result['failed']}")

    payments = load_data("v1/data/payments.json")
    batches = make_batches(payments, 400000, debug=True)
    for batch in batches:
        result = insert_payments(conn, batch, debug=True)
        print(
            f"In batch: inserted={result['inserted']}, failed={result['failed']}, duplicates={result.get('duplicates', 0)}")
    delete_user_alias_csv()


if __name__ == "__main__":
    fill_database()