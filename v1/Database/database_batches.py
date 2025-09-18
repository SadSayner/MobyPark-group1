#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import re
import argparse
from pathlib import Path
from datetime import datetime, timezone
from contextlib import suppress

try:
    import ijson  # streaming JSON parser
except ModuleNotFoundError as e:
    raise SystemExit("Install ijson first: pip install ijson") from e


# ------------------------- Config (defaults) -------------------------
DEFAULT_DB_PATH = "v1\Database\MobyPark.db"
# jouw 2.07 GB JSON: top-level = lijst
DEFAULT_JSON_PATH = "v1\data\payments.json"
DEFAULT_CHUNK_SIZE = 20000               # rijen per executemany
DEFAULT_COMMIT_INTERVAL = 400000         # commit iedere N rijen

# ------------------------- Tijd normalisatie -------------------------


def _to_iso8601(s: str) -> str:
    """
    Converteer 'DD-MM-YYYY HH:MM:UNIX' of plain UNIX (10/13 digits) naar ISO8601 UTC (Z).
    Als er geen UNIX in zit, parse 'DD-MM-YYYY HH:MM' als UTC.
    """
    s = str(s).strip()
    m = re.search(r'(\d{10}|\d{13})$', s)
    if m:
        ts = int(m.group(1))
        if len(m.group(1)) == 13:  # ms -> s
            ts //= 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # fallback: 'DD-MM-YYYY HH:MM'
    dt = datetime.strptime(
        s[:16], "%d-%m-%Y %H:%M").replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_iso(ts):
    """Laat geldige ISO zoals het is; anders converteren met bovengenoemde logica."""
    if not ts:
        return ts
    ts = str(ts).strip()
    try:
        if ts.endswith("Z"):
            datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
            return ts
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return ts
    except Exception:
        return _to_iso8601(ts)


# ------------------------- DB helpers -------------------------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT NOT NULL UNIQUE,
    amount REAL NOT NULL,
    initiator TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed TEXT,
    hash TEXT NOT NULL,
    t_amount REAL,
    t_date TEXT,
    t_method TEXT,
    t_issuer TEXT,
    t_bank TEXT
);
"""

UNIQUE_INDEX_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS ux_payments_transaction_id
ON payments(transaction_id);
"""

DEDUP_SQL = """
DELETE FROM payments
WHERE transaction_id IN (
    SELECT transaction_id
    FROM payments
    GROUP BY transaction_id
    HAVING COUNT(*) > 1
)
AND id NOT IN (
    SELECT MAX(id)
    FROM payments
    GROUP BY transaction_id
);
"""


def sqlite_supports_upsert() -> bool:
    # ON CONFLICT DO UPDATE requires SQLite >= 3.24.0
    return sqlite3.sqlite_version_info >= (3, 24, 0)


def get_insert_sql() -> str:
    if sqlite_supports_upsert():
        return """
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
    else:
        # Fallback: accepteert geen updates; slaat bestaande transaction_id’s over
        return """
        INSERT OR IGNORE INTO payments (
            transaction_id, amount, initiator, created_at, completed, hash,
            t_amount, t_date, t_method, t_issuer, t_bank
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """


def open_db(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    # Performance pragmas (nog steeds redelijk veilig)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute("PRAGMA wal_autocheckpoint=10000;")  # tune naar wens
    return con


def ensure_schema_and_unique(con: sqlite3.Connection):
    """Maak schema; dedupliceer en forceer UNIQUE index op transaction_id."""
    with con:
        con.executescript(SCHEMA_SQL)

        # Probeer eerst UNIQUE index. Faalt deze door duplicaten? Dan dedup + retry.
        try:
            con.execute(UNIQUE_INDEX_SQL)
        except sqlite3.IntegrityError:
            con.execute(DEDUP_SQL)
            con.execute(UNIQUE_INDEX_SQL)


def payment_record_to_tuple(rec: dict):
    """
    Map inkomend record (met nested t_data) naar tuple voor DB.
    Voorbeeld rec:
    {
      'transaction': '...', 'amount': 5.5, 'initiator': '...',
      'created_at': '22-05-2025 09:09:1747898315', 'completed': '...', 'hash': '...',
      't_data': {'amount': 5.5, 'date': '2025-05-22 22:22:22', 'method': 'ideal', 'issuer': 'XYY...', 'bank': 'ABN-NL'}
    }
    """
    t = rec.get("t_data") or {}
    return (
        (rec.get("transaction") or rec.get("transaction_id")),
        float(rec.get("amount") or 0.0),
        rec.get("initiator"),
        _normalize_iso(rec.get("created_at")),
        _normalize_iso(rec.get("completed")),
        rec.get("hash"),
        (None if t.get("amount") in (None, "") else float(t.get("amount"))),
        _normalize_iso(t.get("date")),
        t.get("method"),
        t.get("issuer"),
        t.get("bank"),
    )


def iter_json_array_stream(file_path: str):
    """
    Stream elk element uit een GROOT JSON-bestand met top-level: lijst.
    Voor NDJSON gebruik je ijson.items(f, '') of een eigen regelparser; maar hier is top-level list.
    """
    with open(file_path, "rb") as f:
        for item in ijson.items(f, "item"):
            yield item


def insert_payments_bulk_streaming(conn: sqlite3.Connection,
                                   payments_iter,
                                   chunk_size: int,
                                   commit_interval: int):
    sql = get_insert_sql()
    total = 0
    batch = []

    try:
        conn.execute("BEGIN IMMEDIATE;")
        for rec in payments_iter:
            try:
                batch.append(payment_record_to_tuple(rec))
            except Exception as e:
                # Log en sla over; wil je strikter zijn -> raise
                print(f"[SKIP] invalid record: {e} -> {repr(rec)[:200]}")
                continue

            if len(batch) >= chunk_size:
                conn.executemany(sql, batch)
                total += len(batch)
                batch.clear()

                if total % commit_interval == 0:
                    conn.commit()
                    with suppress(Exception):
                        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                    conn.execute("BEGIN IMMEDIATE;")
                    print(f"[INFO] committed {total} rows...")

        if batch:
            conn.executemany(sql, batch)
            total += len(batch)
            batch.clear()

        conn.commit()
        with suppress(Exception):
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")

    except Exception:
        conn.rollback()
        raise
    return total

# ------------------------- Main -------------------------


def main():
    p = argparse.ArgumentParser(
        description="Stream payments JSON list into SQLite (fast, low RAM).")
    p.add_argument("--db", default=DEFAULT_DB_PATH,
                   help="Pad naar SQLite DB (default: payments.db)")
    p.add_argument("--json", default=DEFAULT_JSON_PATH,
                   help="Pad naar JSON bestand (top-level lijst).")
    p.add_argument("--chunk", type=int, default=DEFAULT_CHUNK_SIZE,
                   help="Rows per batch (executemany).")
    p.add_argument("--commit", type=int, default=DEFAULT_COMMIT_INTERVAL,
                   help="Commit interval in rows.")
    args = p.parse_args()

    db_path = str(Path(args.db))
    json_path = str(Path(args.json))

    print(
        f"[INFO] SQLite version: {sqlite3.sqlite_version}  | UPSERT: {sqlite_supports_upsert()}")
    print(f"[INFO] DB:   {db_path}")
    print(f"[INFO] JSON: {json_path}")

    con = open_db(db_path)
    ensure_schema_and_unique(con)

    print("[INFO] Start streaming import...")
    total = insert_payments_bulk_streaming(
        con,
        iter_json_array_stream(json_path),
        chunk_size=args.chunk,
        commit_interval=args.commit,
    )
    con.close()
    print(f"[DONE] Inserted/Upserted rows: {total}")


if __name__ == "__main__":
    main()
