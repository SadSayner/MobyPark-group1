
from fastapi import APIRouter, HTTPException, Body, Depends
from typing import Dict, Any
from datetime import datetime

from storage_utils import load_parking_lot_data, save_parking_lot_data, load_json, save_data
from v1.server.deps import require_session, require_admin

router = APIRouter()

def now_str() -> str:
    return datetime.now().strftime("%d-%m-%Y %H:%M:%S")

@router.post("/parking-lots")
def create_parking_lot(data: Dict[str, Any] = Body(...), admin = Depends(require_admin)):
    parking_lots = load_parking_lot_data()
    new_lid = str(len(parking_lots) + 1)
    parking_lots[new_lid] = data
    save_parking_lot_data(parking_lots)
    return {"message": f"Parking lot saved under ID: {new_lid}", "id": new_lid}

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
    filtered = {k: v for k, v in sessions.items() if v.get("licenseplate") == data["licenseplate"] and not v.get("stopped")}
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
    filtered = {k: v for k, v in sessions.items() if v.get("licenseplate") == data["licenseplate"] and not v.get("stopped")}
    if not filtered:
        raise HTTPException(400, detail="Cannot stop a session when there is no active session for this licenseplate.")
    sid = next(iter(filtered))
    sessions[sid]["stopped"] = now_str()
    save_data(f"data/pdata/p{lid}-sessions.json", sessions)
    return {"message": f"Session stopped for: {data['licenseplate']}", "id": sid, "session": sessions[sid]}

@router.get("/parking-lots/{lid}/sessions")
def list_sessions(lid: str, user = Depends(require_session)):
    sessions = load_json(f"data/pdata/p{lid}-sessions.json") or {}
    if user.get("role") == "ADMIN":
        return sessions
    return {sid: s for sid, s in sessions.items() if s.get("user") == user["username"]}

@router.get("/parking-lots/{lid}/sessions/{sid}")
def get_session_detail(lid: str, sid: str, user = Depends(require_session)):
    sessions = load_json(f"data/pdata/p{lid}-sessions.json") or {}
    if sid not in sessions:
        raise HTTPException(404, detail="Session not found")
    s = sessions[sid]
    if user.get("role") != "ADMIN" and s.get("user") != user["username"]:
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
