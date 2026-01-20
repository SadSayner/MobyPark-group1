from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import sqlite3

from ..deps import require_session, require_admin
from ...Database.database_logic import get_db, get_user_id_by_username, update_vehicle, delete_vehicle
from ..logging_config import log_event

router = APIRouter()


def now_str() -> str:
    return datetime.now().strftime("%d-%m-%Y %H:%M:%S")


class VehicleIn(BaseModel):
    license_plate: str
    make: str
    model: str
    color: str
    year: int

class UpdateVehicleIn(BaseModel):
    license_plate: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    color: Optional[str] = None
    year: Optional[int] = None


def _mk_lid(plate: str) -> str:
    return (plate or "").replace("-", "").lower()


@router.post("/vehicles")
def create_vehicle(payload: VehicleIn, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    # Use database function to get user ID
    uid = get_user_id_by_username(con, user.get("username"))
    if not uid:
        log_event("ERROR", event="vehicle_create_failed",
                  message="user_not_found")
        raise HTTPException(400, detail="User not found")

    lid = _mk_lid(payload.license_plate)
    # check duplicate for this user using user_vehicles junction table
    exists = con.execute(
        """
        SELECT v.id FROM vehicles v
        JOIN user_vehicles uv ON v.id = uv.vehicle_id
        WHERE uv.user_id = ? AND lower(replace(v.license_plate,'-','')) = ?
        """,
        (uid, lid)
    ).fetchone()
    if exists:
        log_event(
            "WARNING",
            event="vehicle_create_failed",
            username=user.get("username"),
            message="vehicle_exists",
            vehicle_id=exists["id"]
        )
        raise HTTPException(
            400, detail={"error": "Vehicle already exists", "id": exists["id"]})

    created_at = now_str()
    # Insert into vehicles table with all fields
    con.execute(
        """
        INSERT INTO vehicles (license_plate, make, model, color, year, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (payload.license_plate, payload.make, payload.model, payload.color, payload.year, created_at),
    )
    vid = con.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

    # Link vehicle to user in user_vehicles
    con.execute("INSERT INTO user_vehicles (user_id, vehicle_id) VALUES (?, ?)", (uid, vid))
    con.commit()

    vehicle = {
        "id": vid,
        "license_plate": payload.license_plate,
        "make": payload.make,
        "model": payload.model,
        "color": payload.color,
        "year": payload.year,
        "created_at": created_at,
    }
    return vehicle


@router.put("/vehicles/{lid}")
def update_vehicle_route(lid: str, payload: UpdateVehicleIn, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    # Use database function to get user ID
    uid = get_user_id_by_username(con, user.get("username"))
    if not uid:
        log_event("ERROR", event="vehicle_update_failed",
                  message="user_not_found")
        raise HTTPException(400, detail="User not found")

    # Look up vehicle by id (lid parameter is the vehicle ID from tests)
    row = con.execute(
        """
        SELECT v.* FROM vehicles v
        JOIN user_vehicles uv ON v.id = uv.vehicle_id
        WHERE uv.user_id = ? AND v.id = ?
        """,
        (uid, int(lid))
    ).fetchone()

    if not row:
        log_event("WARNING", event="vehicle_update_failed",
                  message="vehicle_not_found", vehicle_id=lid)
        raise HTTPException(404, detail="Vehicle not found")

    # Build update query dynamically for provided fields
    updates = []
    params = []
    if payload.license_plate is not None:
        updates.append("license_plate = ?")
        params.append(payload.license_plate)
    if payload.make is not None:
        updates.append("make = ?")
        params.append(payload.make)
    if payload.model is not None:
        updates.append("model = ?")
        params.append(payload.model)
    if payload.color is not None:
        updates.append("color = ?")
        params.append(payload.color)
    if payload.year is not None:
        updates.append("year = ?")
        params.append(payload.year)

    if updates:
        params.append(row["id"])
        sql = f"UPDATE vehicles SET {', '.join(updates)} WHERE id = ?"
        con.execute(sql, params)
        con.commit()

    updated = con.execute("SELECT * FROM vehicles WHERE id = ?", (row["id"],)).fetchone()
    v = dict(updated)
    return {
        "id": v.get("id"),
        "license_plate": v.get("license_plate"),
        "make": v.get("make"),
        "model": v.get("model"),
        "color": v.get("color"),
        "year": v.get("year"),
        "created_at": v.get("created_at")
    }


@router.delete("/vehicles/{lid}")
def delete_vehicle_route(lid: str, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    # Use database function to get user ID
    uid = get_user_id_by_username(con, user.get("username"))
    if not uid:
        log_event("ERROR", event="vehicle_delete_failed",
                  message="user_not_found")
        raise HTTPException(400, detail="User not found")

    # Look up vehicle by id
    row = con.execute(
        """
        SELECT v.id FROM vehicles v
        JOIN user_vehicles uv ON v.id = uv.vehicle_id
        WHERE uv.user_id = ? AND v.id = ?
        """,
        (uid, int(lid))
    ).fetchone()
    if not row:
        log_event("WARNING", event="vehicle_delete_failed",
                  message="vehicle_not_found", vehicle_id=lid)
        raise HTTPException(404, detail="Vehicle not found")

    # Delete from user_vehicles junction table
    con.execute("DELETE FROM user_vehicles WHERE user_id = ? AND vehicle_id = ?", (uid, row["id"]))
    con.commit()

    return {"message": "Vehicle deleted"}


@router.get("/vehicles")
def list_own_vehicles(user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    # Use database function to get user ID
    uid = get_user_id_by_username(con, user.get("username"))
    if not uid:
        return []
    rows = con.execute(
        """
        SELECT v.* FROM vehicles v
        JOIN user_vehicles uv ON v.id = uv.vehicle_id
        WHERE uv.user_id = ?
        ORDER BY v.created_at DESC
        """,
        (uid,)
    ).fetchall()
    result = []
    for r in rows:
        v = dict(r)
        result.append({
            "id": v.get("id"),
            "license_plate": v.get("license_plate"),
            "make": v.get("make"),
            "model": v.get("model"),
            "color": v.get("color"),
            "year": v.get("year"),
            "created_at": v.get("created_at")
        })
    return result


@router.get("/vehicles/{user_name}")
def list_user_vehicles(user_name: str, admin = Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    # Use database function to get user ID
    uid = get_user_id_by_username(con, user_name)
    if not uid:
        log_event("WARNING", event="vehicle_list_admin_failed",
                  message="user_not_found", target_user=user_name)
        raise HTTPException(404, detail="User not found")
    rows = con.execute(
        """
        SELECT v.* FROM vehicles v
        JOIN user_vehicles uv ON v.id = uv.vehicle_id
        WHERE uv.user_id = ?
        ORDER BY v.created_at DESC
        """,
        (uid,)
    ).fetchall()
    result: Dict[str, Any] = {}
    for r in rows:
        v = dict(r)
        key = _mk_lid(v.get("license_plate") or "")
        result[key] = {"id": v.get("id"), "licenseplate": v.get("license_plate"), "name": v.get("make"), "created_at": v.get("created_at")}
    return result


@router.post("/vehicles/{lid}/entry")
def vehicle_entry(lid: str, data: Dict[str, Any] = Body(...), user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    if "parkinglot" not in data:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "parkinglot"})
    # Use database function to get user ID
    uid = get_user_id_by_username(con, user.get("username"))
    if not uid:
        raise HTTPException(400, detail="User not found")

    norm_lid = _mk_lid(lid)
    vrow = con.execute(
        """
        SELECT v.* FROM vehicles v
        JOIN user_vehicles uv ON v.id = uv.vehicle_id
        WHERE uv.user_id = ? AND lower(replace(v.license_plate,'-','')) = ?
        """,
        (uid, norm_lid)
    ).fetchone()
    if not vrow:
        raise HTTPException(400, detail={"error": "Vehicle does not exist", "data": lid})
    v = dict(vrow)
    return {"status": "Accepted", "vehicle": {"licenseplate": v.get("license_plate"), "name": v.get("make")}}


@router.get("/vehicles/{vid}/reservations")
def vehicle_reservations(vid: str, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    # Use database function to get user ID
    uid = get_user_id_by_username(con, user.get("username"))
    if not uid:
        raise HTTPException(400, detail="User not found")

    norm_vid = _mk_lid(vid)
    vrow = con.execute(
        """
        SELECT v.* FROM vehicles v
        JOIN user_vehicles uv ON v.id = uv.vehicle_id
        WHERE uv.user_id = ? AND lower(replace(v.license_plate,'-','')) = ?
        """,
        (uid, norm_vid)
    ).fetchone()
    if not vrow:
        raise HTTPException(404, detail="Not found")

    # placeholder: return empty list (no DB reservations linked in current schema)
    return []


@router.get("/vehicles/{vid}/history")
def vehicle_history(vid: str, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    # Use database function to get user ID
    uid = get_user_id_by_username(con, user.get("username"))
    if not uid:
        raise HTTPException(400, detail="User not found")

    norm_vid = _mk_lid(vid)
    vrow = con.execute(
        """
        SELECT v.* FROM vehicles v
        JOIN user_vehicles uv ON v.id = uv.vehicle_id
        WHERE uv.user_id = ? AND lower(replace(v.license_plate,'-','')) = ?
        """,
        (uid, norm_vid)
    ).fetchone()
    if not vrow:
        raise HTTPException(404, detail="Not found")

    # placeholder: return empty list (no vehicle history table in current schema)
    return []