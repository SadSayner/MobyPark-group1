
from fastapi import APIRouter, HTTPException, Body, Depends
from typing import Dict, Any
from datetime import datetime
import sqlite3

from storage_utils import load_parking_lot_data, save_parking_lot_data, load_json, save_data
from server.deps import require_session, require_admin
from Database.database_logic import get_db, get_parking_lot_by_id, get_all_parking_lots, update_parking_lot, delete_parking_lot

router = APIRouter()

def now_str() -> str:
    return datetime.now().strftime("%d-%m-%Y %H:%M:%S")

def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}

@router.post("/parking-lots")
def create_parking_lot(data: Dict[str, Any] = Body(...), admin = Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute(
        """
        INSERT INTO parking_lots (name, location, address, capacity, reserved, tariff, daytariff, created_at, lat, lng)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("name"),
            data.get("location"),
            data.get("address"),
            data.get("capacity"),
            int(bool(data.get("reserved"))) if "reserved" in data else 0,
            data.get("tariff"),
            data.get("daytariff"),
            now_str(),
            data.get("lat"),
            data.get("lng"),
        ),
    )
    con.commit()
    new_id = cur.lastrowid
    return {"message": f"Parking lot saved under ID: {new_id}", "id": new_id}

@router.post("/parking-lots")
def create_parking_lot(data: Dict[str, Any] = Body(...), admin = Depends(require_admin),
                       con: sqlite3.Connection = Depends(get_db)):
    # map allowed fields; missing fields get NULL / defaults
    cur = con.execute(
        """
        INSERT INTO parking_lots (name, location, address, capacity, reserved, tariff, daytariff, created_at, lat, lng)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("name"),
            data.get("location"),
            data.get("address"),
            data.get("capacity"),
            int(bool(data.get("reserved"))) if "reserved" in data else 0,
            data.get("tariff"),
            data.get("daytariff"),
            now_str(),
            data.get("lat"),
            data.get("lng"),
        ),
    )
    con.commit()
    new_id = cur.lastrowid
    return {"message": f"Parking lot saved under ID: {new_id}", "id": new_id}

#Body(...) betekent dat de body verplicht is
@router.put("/parking-lots/{lid}")
def update_parking_lot_route(lid: str, data: Dict[str, Any] = Body(...), admin = Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    # Check if parking lot exists
    parking_lot = get_parking_lot_by_id(con, int(lid))
    if parking_lot is None:
        raise HTTPException(404, detail="Parking lot not found")

    # Build updates dictionary with fallbacks to existing values
    updates = {
        "name": data.get("name", parking_lot.name),
        "location": data.get("location", parking_lot.location),
        "address": data.get("address", parking_lot.address),
        "capacity": data.get("capacity", parking_lot.capacity),
        "reserved": int(bool(data.get("reserved", parking_lot.reserved))) if "reserved" in data else parking_lot.reserved,
        "tariff": data.get("tariff", parking_lot.tariff),
        "daytariff": data.get("daytariff", parking_lot.daytariff),
        "lat": data.get("lat", parking_lot.lat),
        "lng": data.get("lng", parking_lot.lng),
    }

    # Use database function
    success = update_parking_lot(con, int(lid), updates)
    if not success:
        raise HTTPException(500, detail="Failed to update parking lot")

    return {"message": "Parking lot modified"}

@router.delete("/parking-lots/{lid}")
def delete_parking_lot_route(lid: str, admin = Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    # Use database function
    success = delete_parking_lot(con, int(lid))
    if not success:
        raise HTTPException(404, detail="Parking lot not found")
    return {"message": "Parking lot deleted"}

@router.get("/parking-lots")
def list_parking_lots(con: sqlite3.Connection = Depends(get_db)):
    # Use database function
    parking_lots = get_all_parking_lots(con)
    # Convert model objects to dicts
    return [lot.to_dict() for lot in parking_lots]

@router.get("/parking-lots/{lid}")
def get_parking_lot_route(lid: str, con: sqlite3.Connection = Depends(get_db)):
    # Use database function
    parking_lot = get_parking_lot_by_id(con, int(lid))
    if parking_lot is None:
        raise HTTPException(404, detail="Parking lot not found")
    return parking_lot.to_dict()

# Sessions for parking lots
@router.post("/parking-lots/{lid}/sessions/start")
def start_session(lid: str, data: Dict[str, Any] = Body(...), user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    if "licenseplate" not in data:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "licenseplate"})

    # Get user ID
    from Database.database_logic import get_user_id_by_username
    user_id = get_user_id_by_username(con, user["username"])
    if not user_id:
        raise HTTPException(400, detail="User not found")

    # Find or create vehicle with this license plate
    license_plate = data["licenseplate"]
    cur = con.execute("SELECT id FROM vehicles WHERE license_plate = ? AND user_id = ?", (license_plate, user_id))
    vehicle_row = cur.fetchone()

    if not vehicle_row:
        # Create vehicle if it doesn't exist
        con.execute(
            "INSERT INTO vehicles (user_id, license_plate, created_at) VALUES (?, ?, ?)",
            (user_id, license_plate, now_str())
        )
        vehicle_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    else:
        vehicle_id = vehicle_row["id"]

    # Check for active sessions with this vehicle
    cur = con.execute("SELECT * FROM sessions WHERE parking_lot_id = ? AND vehicle_id = ? AND stopped IS NULL", (lid, vehicle_id))
    active_session = cur.fetchone()
    if active_session:
        raise HTTPException(400, detail="Cannot start a session when another session for this vehicle is already active.")

    # Insert new session
    started = now_str()
    cur = con.execute(
        "INSERT INTO sessions (parking_lot_id, user_id, vehicle_id, started, payment_status) VALUES (?, ?, ?, ?, ?)",
        (lid, user_id, vehicle_id, started, "unpaid")
    )
    con.commit()
    session_id = cur.lastrowid

    return {"message": f"Session started for: {license_plate}", "id": session_id, "session": {
        "session_id": session_id,
        "parking_lot_id": lid,
        "user_id": user_id,
        "vehicle_id": vehicle_id,
        "started": started,
        "stopped": None,
        "payment_status": "unpaid"
    }}

@router.post("/parking-lots/{lid}/sessions/stop")
def stop_session(lid: str, data: Dict[str, Any] = Body(...), user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    if "licenseplate" not in data:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "licenseplate"})

    # Get user ID
    from Database.database_logic import get_user_id_by_username
    user_id = get_user_id_by_username(con, user["username"])
    if not user_id:
        raise HTTPException(400, detail="User not found")

    # Find vehicle
    license_plate = data["licenseplate"]
    cur = con.execute("SELECT id FROM vehicles WHERE license_plate = ? AND user_id = ?", (license_plate, user_id))
    vehicle_row = cur.fetchone()
    if not vehicle_row:
        raise HTTPException(404, detail="Vehicle not found")
    vehicle_id = vehicle_row["id"]

    # Find active session
    cur = con.execute(
        "SELECT * FROM sessions WHERE parking_lot_id = ? AND vehicle_id = ? AND stopped IS NULL",
        (lid, vehicle_id)
    )
    active_session = cur.fetchone()
    if not active_session:
        raise HTTPException(400, detail="Cannot stop a session when there is no active session for this vehicle.")

    # Stop the session
    stopped = now_str()
    session_id = active_session["session_id"]
    con.execute("UPDATE sessions SET stopped = ? WHERE session_id = ?", (stopped, session_id))
    con.commit()

    return {"message": f"Session stopped for: {license_plate}", "id": session_id}

@router.get("/parking-lots/{lid}/sessions")
def list_sessions(lid: str, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    # Get user ID
    from Database.database_logic import get_user_id_by_username
    user_id = get_user_id_by_username(con, user["username"])

    cur = con.execute("SELECT * FROM sessions WHERE parking_lot_id = ?", (lid,))
    sessions = cur.fetchall()

    if user["role"] == "ADMIN":
        return [dict(s) for s in sessions]

    # Filter to user's sessions
    user_sessions = [dict(s) for s in sessions if s["user_id"] == user_id]
    return user_sessions

@router.get("/parking-lots/{lid}/sessions/{sid}")
def get_session_detail(lid: str, sid: str, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    # Get user ID
    from Database.database_logic import get_user_id_by_username
    user_id = get_user_id_by_username(con, user["username"])

    cur = con.execute("SELECT * FROM sessions WHERE parking_lot_id = ? AND session_id = ?", (lid, sid))
    session = cur.fetchone()
    if session is None:
        raise HTTPException(404, detail="Session not found")
    if user["role"] != "ADMIN" and session["user_id"] != user_id:
        raise HTTPException(403, detail="Access denied")
    return dict(session)

@router.delete("/parking-lots/{lid}/sessions/{sid}")
def delete_session(lid: str, sid: str, admin = Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute("SELECT * FROM sessions WHERE parking_lot_id = ? AND session_id = ?", (lid, sid))
    session = cur.fetchone()
    if session is None:
        raise HTTPException(404, detail="Session not found")
    con.execute("DELETE FROM sessions WHERE session_id = ?", (sid,))
    con.commit()
    return {"message": "Session deleted"}
