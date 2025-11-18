
from fastapi import APIRouter, HTTPException, Body, Depends
from typing import Dict, Any
from datetime import datetime
import sqlite3

from storage_utils import load_parking_lot_data, save_parking_lot_data, load_json, save_data
from v1.server.deps import require_session, require_admin
from v1.Database.database_logic import get_db

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
def update_parking_lot(lid: str, data: Dict[str, Any] = Body(...), admin = Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute("SELECT * FROM parking_lots WHERE id = ?", (lid,))
    parking_lot = cur.fetchone()
    if parking_lot is None:
        raise HTTPException(404, detail="Parking lot not found")
    con.execute(
        """
        UPDATE parking_lots SET name = ?, location = ?, address = ?, capacity = ?, reserved = ?, tariff = ?, daytariff = ?, lat = ?, lng = ?
        WHERE id = ?
        """,
        (
            data.get("name", parking_lot["name"]),
            data.get("location", parking_lot["location"]),
            data.get("address", parking_lot["address"]),
            data.get("capacity", parking_lot["capacity"]),
            int(bool(data.get("reserved", parking_lot["reserved"]))) if "reserved" in data else 0,
            data.get("tariff", parking_lot["tariff"]),
            data.get("daytariff", parking_lot["daytariff"]),
            data.get("lat", parking_lot["lat"]),
            data.get("lng", parking_lot["lng"]),
            lid
        ),
    )
    con.commit()
    return {"message": "Parking lot modified"}

@router.delete("/parking-lots/{lid}")
def delete_parking_lot(lid: str, admin = Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute("SELECT * FROM parking_lots WHERE id = ?", (lid,))
    parking_lot = cur.fetchone()
    if parking_lot is None:
        raise HTTPException(404, detail="Parking lot not found")
    con.execute("DELETE FROM parking_lots WHERE id = ?", (lid,))
    con.commit()
    return {"message": "Parking lot deleted"}

@router.get("/parking-lots")
def list_parking_lots(con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute("SELECT * FROM parking_lots")
    rows = cur.fetchall()
    return [row_to_dict(row) for row in rows]

@router.get("/parking-lots/{lid}")
def get_parking_lot(lid: str, con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute("SELECT * FROM parking_lots WHERE id = ?", (lid,))
    parking_lot = cur.fetchone()
    if parking_lot is None:
        raise HTTPException(404, detail="Parking lot not found")
    return row_to_dict(parking_lot)

# Sessions for parking lots
@router.post("/parking-lots/{lid}/sessions/start")
def start_session(lid: str, data: Dict[str, Any] = Body(...), user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    if "licenseplate" not in data:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "licenseplate"})
    cur = con.execute("SELECT * FROM parking_sessions WHERE parking_lot_id = ?", (lid,))
    sessions = cur.fetchall()
    filtered = {}
    for v in sessions:
        lp = v.get("licenseplate")
        stopped = v.get("stopped")
        if lp == data["licenseplate"] and not stopped:
            filtered[v["id"]] = v
    if filtered:
        raise HTTPException(400, detail="Cannot start a session when another session for this licenseplate is already started.")
    session = {"licenseplate": data["licenseplate"], "started": now_str(), "stopped": None, "user": user["username"]}
    cur = con.execute("INSERT INTO parking_sessions (licenseplate, started, stopped, user, parking_lot_id) VALUES (?, ?, ?, ?, ?)",
                      (session["licenseplate"], session["started"], session["stopped"], session["user"], lid))
    con.commit()
    session["id"] = cur.lastrowid
    return {"message": f"Session started for: {data['licenseplate']}", "id": session["id"], "session": session}

@router.post("/parking-lots/{lid}/sessions/stop")
def stop_session(lid: str, data: Dict[str, Any] = Body(...), user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    if "licenseplate" not in data:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "licenseplate"})
    cur = con.execute("SELECT * FROM parking_sessions WHERE parking_lot_id = ?", (lid,))
    sessions = cur.fetchall()
    filtered = {}
    for v in sessions:
        lp = v.get("licenseplate")
        stopped = v.get("stopped")
        if lp == data["licenseplate"] and not stopped:
            filtered[v["id"]] = v
    if not filtered:
        raise HTTPException(400, detail="Cannot stop a session when there is no active session for this licenseplate.")
    sid = next(iter(filtered))
    cur.execute("UPDATE parking_sessions SET stopped = ? WHERE id = ?", (now_str(), sid))
    con.commit()
    return {"message": f"Session stopped for: {data['licenseplate']}", "id": sid, "session": sessions[sid]}

@router.get("/parking-lots/{lid}/sessions")
def list_sessions(lid: str, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute("SELECT * FROM parking_sessions WHERE parking_lot_id = ?", (lid,))
    sessions = cur.fetchall()
    if user["role"] == "ADMIN":
        return sessions
    
    user_sessions = {}
    for s in sessions:
        if s["user"] == user["username"]:
            user_sessions[s["id"]] = s
    return user_sessions

@router.get("/parking-lots/{lid}/sessions/{sid}")
def get_session_detail(lid: str, sid: str, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute("SELECT * FROM parking_sessions WHERE parking_lot_id = ? AND id = ?", (lid, sid))
    session = cur.fetchone()
    if session is None:
        raise HTTPException(404, detail="Session not found")
    if user["role"] != "ADMIN" and session["user"] != user["username"]:
        raise HTTPException(403, detail="Access denied")
    return session

@router.delete("/parking-lots/{lid}/sessions/{sid}")
def delete_session(lid: str, sid: str, admin = Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute("SELECT * FROM parking_sessions WHERE parking_lot_id = ? AND id = ?", (lid, sid))
    session = cur.fetchone()
    if session is None:
        raise HTTPException(404, detail="Session not found")
    cur.execute("DELETE FROM parking_sessions WHERE id = ?", (sid,))
    con.commit()
    return {"message": "Session deleted"}
