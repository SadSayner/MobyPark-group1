from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import sqlite3

from v1.server.deps import require_session, require_admin
from v1.Database.database_logic import get_db

router = APIRouter()


def now_str() -> str:
    return datetime.now().strftime("%d-%m-%Y %H:%M:%S")


class VehicleIn(BaseModel):
    name: str
    license_plate: Optional[str] = None


def _mk_lid(plate: str) -> str:
    return (plate or "").replace("-", "").lower()


@router.post("/vehicles")
def create_vehicle(payload: VehicleIn, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    # basic validation
    if not payload.name or not payload.license_plate:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "name/license_plate"})
    # resolve user id
    cur = con.execute("SELECT id FROM users WHERE username = ?", (user.get("username"),))
    urow = cur.fetchone()
    if not urow:
        raise HTTPException(400, detail="User not found")
    uid = urow["id"]

    lid = _mk_lid(payload.license_plate)
    # check duplicate for this user
    exists = con.execute(
        "SELECT id FROM vehicles WHERE user_id = ? AND lower(replace(license_plate,'-','')) = ?",
        (uid, lid)
    ).fetchone()
    if exists:
        raise HTTPException(400, detail={"error": "Vehicle already exists", "id": exists["id"]})

    created_at = now_str()
    con.execute(
        """
        INSERT INTO vehicles (user_id, license_plate, name, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (uid, payload.license_plate, payload.name, created_at, created_at),
    )
    con.commit()
    vid = con.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

    vehicle = {
        "id": vid,
        "licenseplate": payload.license_plate,
        "name": payload.name,
        "created_at": created_at,
        "updated_at": created_at,
    }
    return {"status": "Success", "vehicle": vehicle}


@router.put("/vehicles/{lid}")
def update_vehicle(lid: str, payload: VehicleIn, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    if not payload.name:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "name"})
    cur = con.execute("SELECT id FROM users WHERE username = ?", (user.get("username"),))
    urow = cur.fetchone()
    if not urow:
        raise HTTPException(400, detail="User not found")
    uid = urow["id"]

    norm_lid = _mk_lid(lid)
    row = con.execute(
        "SELECT * FROM vehicles WHERE user_id = ? AND lower(replace(license_plate,'-','')) = ?",
        (uid, norm_lid)
    ).fetchone()

    now = now_str()
    if not row:
        # create new vehicle record for this user
        if not payload.license_plate:
            # if no explicit license_plate provided in body, use lid param
            license_plate = lid
        else:
            license_plate = payload.license_plate
        con.execute(
            "INSERT INTO vehicles (user_id, license_plate, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (uid, license_plate, payload.name, now, now),
        )
        con.commit()
        vid = con.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        vehicle = {"id": vid, "licenseplate": license_plate, "name": payload.name, "created_at": now, "updated_at": now}
        return {"status": "Success", "vehicle": vehicle}

    # update existing
    con.execute(
        "UPDATE vehicles SET name = ?, updated_at = ? WHERE id = ?",
        (payload.name, now, row["id"]),
    )
    con.commit()
    updated = con.execute("SELECT * FROM vehicles WHERE id = ?", (row["id"],)).fetchone()
    v = dict(updated)
    return {"status": "Success", "vehicle": {"id": v.get("id"), "licenseplate": v.get("license_plate"), "name": v.get("name"), "created_at": v.get("created_at"), "updated_at": v.get("updated_at") }}


@router.delete("/vehicles/{lid}")
def delete_vehicle(lid: str, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute("SELECT id FROM users WHERE username = ?", (user.get("username"),))
    urow = cur.fetchone()
    if not urow:
        raise HTTPException(400, detail="User not found")
    uid = urow["id"]

    norm_lid = _mk_lid(lid)
    row = con.execute(
        "SELECT id FROM vehicles WHERE user_id = ? AND lower(replace(license_plate,'-','')) = ?",
        (uid, norm_lid)
    ).fetchone()
    if not row:
        raise HTTPException(404, detail="Vehicle not found")
    con.execute("DELETE FROM vehicles WHERE id = ?", (row["id"],))
    con.commit()
    return {"status": "Deleted"}


@router.get("/vehicles")
def list_own_vehicles(user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute("SELECT id FROM users WHERE username = ?", (user.get("username"),))
    urow = cur.fetchone()
    if not urow:
        return {}
    uid = urow["id"]
    rows = con.execute("SELECT * FROM vehicles WHERE user_id = ? ORDER BY created_at DESC", (uid,)).fetchall()
    result: Dict[str, Any] = {}
    for r in rows:
        v = dict(r)
        key = _mk_lid(v.get("license_plate") or "")
        result[key] = {"id": v.get("id"), "licenseplate": v.get("license_plate"), "name": v.get("name"), "created_at": v.get("created_at"), "updated_at": v.get("updated_at")}
    return result


@router.get("/vehicles/{user_name}")
def list_user_vehicles(user_name: str, admin = Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute("SELECT id FROM users WHERE username = ?", (user_name,))
    urow = cur.fetchone()
    if not urow:
        raise HTTPException(404, detail="User not found")
    uid = urow["id"]
    rows = con.execute("SELECT * FROM vehicles WHERE user_id = ? ORDER BY created_at DESC", (uid,)).fetchall()
    result: Dict[str, Any] = {}
    for r in rows:
        v = dict(r)
        key = _mk_lid(v.get("license_plate") or "")
        result[key] = {"id": v.get("id"), "licenseplate": v.get("license_plate"), "name": v.get("name"), "created_at": v.get("created_at"), "updated_at": v.get("updated_at")}
    return result


@router.post("/vehicles/{lid}/entry")
def vehicle_entry(lid: str, data: Dict[str, Any] = Body(...), user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    if "parkinglot" not in data:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "parkinglot"})
    cur = con.execute("SELECT id FROM users WHERE username = ?", (user.get("username"),))
    urow = cur.fetchone()
    if not urow:
        raise HTTPException(400, detail="User not found")
    uid = urow["id"]

    norm_lid = _mk_lid(lid)
    vrow = con.execute("SELECT * FROM vehicles WHERE user_id = ? AND lower(replace(license_plate,'-','')) = ?", (uid, norm_lid)).fetchone()
    if not vrow:
        raise HTTPException(400, detail={"error": "Vehicle does not exist", "data": lid})
    v = dict(vrow)
    # no DB action required here in original; just accept
    return {"status": "Accepted", "vehicle": {"licenseplate": v.get("license_plate"), "name": v.get("name") }}


@router.get("/vehicles/{vid}/reservations")
def vehicle_reservations(vid: str, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute("SELECT id FROM users WHERE username = ?", (user.get("username"),))
    urow = cur.fetchone()
    if not urow:
        raise HTTPException(400, detail="User not found")
    uid = urow["id"]

    norm_vid = _mk_lid(vid)
    vrow = con.execute("SELECT * FROM vehicles WHERE user_id = ? AND lower(replace(license_plate,'-','')) = ?", (uid, norm_vid)).fetchone()
    if not vrow:
        raise HTTPException(404, detail="Not found")

    # placeholder: return empty list (no DB reservations linked in current schema)
    return []


@router.get("/vehicles/{vid}/history")
def vehicle_history(vid: str, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute("SELECT id FROM users WHERE username = ?", (user.get("username"),))
    urow = cur.fetchone()
    if not urow:
        raise HTTPException(400, detail="User not found")
    uid = urow["id"]

    norm_vid = _mk_lid(vid)
    vrow = con.execute("SELECT * FROM vehicles WHERE user_id = ? AND lower(replace(license_plate,'-','')) = ?", (uid, norm_vid)).fetchone()
    if not vrow:
        raise HTTPException(404, detail="Not found")

    # placeholder: return empty list (no vehicle history table in current schema)
    return []
# ...existing code...