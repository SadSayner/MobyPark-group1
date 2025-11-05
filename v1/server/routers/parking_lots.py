
from fastapi import APIRouter, HTTPException, Body, Depends
from typing import Dict, Any
from datetime import datetime
import sqlite3

from storage_utils import load_parking_lot_data, save_parking_lot_data, load_json, save_data
from v1.server.deps import require_session, require_admin
from v1.Database.database_logic import get_connection

router = APIRouter()

def now_str() -> str:
    return datetime.now().strftime("%d-%m-%Y %H:%M:%S")

def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


def get_db():
    con = get_connection()
    try:
        yield con
    finally:
        try:
            con.close()
        except Exception:
            pass

@router.post("/parking-lots")
def create_parking_lot(data: Dict[str, Any] = Body(...), admin = Depends(require_admin)):
    parking_lots = load_parking_lot_data()
    new_lid = str(len(parking_lots) + 1)
    parking_lots[new_lid] = data
    save_parking_lot_data(parking_lots)
    return {"message": f"Parking lot saved under ID: {new_lid}", "id": new_lid}

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
def update_parking_lot(lid: str, data: Dict[str, Any] = Body(...), admin = Depends(require_admin)):
    parking_lots = load_parking_lot_data()
    if lid not in parking_lots:
        raise HTTPException(404, detail="Parking lot not found")
    parking_lots[lid] = data
    save_parking_lot_data(parking_lots)
    return {"message": "Parking lot modified"}

@router.delete("/parking-lots/{lid}")
def delete_parking_lot(lid: str, admin = Depends(require_admin)):
    parking_lots = load_parking_lot_data()
    if lid not in parking_lots:
        raise HTTPException(404, detail="Parking lot not found")
    del parking_lots[lid]
    save_parking_lot_data(parking_lots)
    return {"message": "Parking lot deleted"}

@router.get("/parking-lots")
def list_parking_lots():
    return load_parking_lot_data()

@router.get("/parking-lots/{lid}")
def get_parking_lot(lid: str):
    parking_lots = load_parking_lot_data()
    if lid not in parking_lots:
        raise HTTPException(404, detail="Parking lot not found")
    return parking_lots[lid]

# Sessions for parking lots
@router.post("/parking-lots/{lid}/sessions/start")
def start_session(lid: str, data: Dict[str, Any] = Body(...), user = Depends(require_session)):
    if "licenseplate" not in data:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "licenseplate"})
    sessions = load_json(f"data/pdata/p{lid}-sessions.json") or {}
    filtered = {}
    for k, v in sessions.items():
        lp = v.get("licenseplate")
        stopped = v.get("stopped")
        if lp == data["licenseplate"] and not stopped:
            filtered[k] = v
    if filtered:
        raise HTTPException(400, detail="Cannot start a session when another session for this licenseplate is already started.")
    session = {"licenseplate": data["licenseplate"], "started": now_str(), "stopped": None, "user": user["username"]}
    sid = str(len(sessions) + 1)
    sessions[sid] = session
    save_data(f"data/pdata/p{lid}-sessions.json", sessions)
    return {"message": f"Session started for: {data['licenseplate']}", "id": sid, "session": session}

@router.post("/parking-lots/{lid}/sessions/stop")
def stop_session(lid: str, data: Dict[str, Any] = Body(...), user = Depends(require_session)):
    if "licenseplate" not in data:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "licenseplate"})
    sessions = load_json(f"data/pdata/p{lid}-sessions.json") or {}
    filtered = {}
    for k, v in sessions.items():
        lp = v.get("licenseplate")
        stopped = v.get("stopped")
        if lp == data["licenseplate"] and not stopped:
            filtered[k] = v
    if not filtered:
        raise HTTPException(400, detail="Cannot stop a session when there is no active session for this licenseplate.")
    sid = next(iter(filtered))
    sessions[sid]["stopped"] = now_str()
    save_data(f"data/pdata/p{lid}-sessions.json", sessions)
    return {"message": f"Session stopped for: {data['licenseplate']}", "id": sid, "session": sessions[sid]}

@router.get("/parking-lots/{lid}/sessions")
def list_sessions(lid: str, user = Depends(require_session)):
    sessions = load_json(f"data/pdata/p{lid}-sessions.json") or {}
    if user["role"] == "ADMIN":
        return sessions
    
    user_sessions = {}
    for sid, s in sessions.items():
        if s["user"] == user["username"]:
            user_sessions[sid] = s
    return user_sessions

@router.get("/parking-lots/{lid}/sessions/{sid}")
def get_session_detail(lid: str, sid: str, user = Depends(require_session)):
    sessions = load_json(f"data/pdata/p{lid}-sessions.json") or {}
    if sid not in sessions:
        raise HTTPException(404, detail="Session not found")
    s = sessions[sid]
    if user["role"] != "ADMIN" and s["user"] != user["username"]:
        raise HTTPException(403, detail="Access denied")
    return s

@router.delete("/parking-lots/{lid}/sessions/{sid}")
def delete_session(lid: str, sid: str, admin = Depends(require_admin)):
    sessions = load_json(f"data/pdata/p{lid}-sessions.json") or {}
    if sid not in sessions:
        raise HTTPException(404, detail="Session not found")
    del sessions[sid]
    save_data(f"data/pdata/p{lid}-sessions.json", sessions)
    return {"message": "Session deleted"}
