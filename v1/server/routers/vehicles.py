from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import sqlite3

from ..deps import require_session, require_admin
from ...Database.database_logic import get_db, get_user_id_by_username
from logging_config import log_event

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
def create_vehicle(payload: VehicleIn, user=Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    log_event("INFO", event="vehicle_create_attempt",
              username=user.get("username"))

    uid = get_user_id_by_username(con, user.get("username"))
    if not uid:
        log_event("ERROR", event="vehicle_create_failed",
                  reason="user_not_found")
        raise HTTPException(400, detail="User not found")

    lid = _mk_lid(payload.license_plate)

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
            reason="vehicle_exists",
            vehicle_id=exists["id"]
        )
        raise HTTPException(
            400, detail={"error": "Vehicle already exists", "id": exists["id"]})

    created_at = now_str()

    con.execute(
        """
        INSERT INTO vehicles (license_plate, make, model, color, year, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (payload.license_plate, payload.make, payload.model,
         payload.color, payload.year, created_at),
    )
    vid = con.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    con.execute(
        "INSERT INTO user_vehicles (user_id, vehicle_id) VALUES (?, ?)", (uid, vid))
    con.commit()

    log_event(
        "INFO",
        event="vehicle_created",
        username=user.get("username"),
        vehicle_id=vid,
        license_plate=payload.license_plate
    )

    return {
        "id": vid,
        "license_plate": payload.license_plate,
        "make": payload.make,
        "model": payload.model,
        "color": payload.color,
        "year": payload.year,
        "created_at": created_at,
    }


@router.put("/vehicles/{lid}")
def update_vehicle_route(lid: str, payload: UpdateVehicleIn, user=Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    log_event("INFO", event="vehicle_update_attempt",
              username=user.get("username"), vehicle_id=lid)

    uid = get_user_id_by_username(con, user.get("username"))
    if not uid:
        log_event("ERROR", event="vehicle_update_failed",
                  reason="user_not_found")
        raise HTTPException(400, detail="User not found")

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
                  reason="vehicle_not_found", vehicle_id=lid)
        raise HTTPException(404, detail="Vehicle not found")

    updates = []
    params = []

    for field in ["license_plate", "make", "model", "color", "year"]:
        value = getattr(payload, field)
        if value is not None:
            updates.append(f"{field} = ?")
            params.append(value)

    if updates:
        params.append(row["id"])
        sql = f"UPDATE vehicles SET {', '.join(updates)} WHERE id = ?"
        con.execute(sql, params)
        con.commit()

        log_event(
            "INFO",
            event="vehicle_updated",
            username=user.get("username"),
            vehicle_id=row["id"],
            fields=[u.split(" ")[0] for u in updates]
        )

    updated = con.execute(
        "SELECT * FROM vehicles WHERE id = ?", (row["id"],)).fetchone()
    return dict(updated)


@router.delete("/vehicles/{lid}")
def delete_vehicle_route(lid: str, user=Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    log_event("INFO", event="vehicle_delete_attempt",
              username=user.get("username"), vehicle_id=lid)

    uid = get_user_id_by_username(con, user.get("username"))
    if not uid:
        log_event("ERROR", event="vehicle_delete_failed",
                  reason="user_not_found")
        raise HTTPException(400, detail="User not found")

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
                  reason="vehicle_not_found", vehicle_id=lid)
        raise HTTPException(404, detail="Vehicle not found")

    con.execute(
        "DELETE FROM user_vehicles WHERE user_id = ? AND vehicle_id = ?", (uid, row["id"]))
    con.commit()

    log_event(
        "INFO",
        event="vehicle_deleted",
        username=user.get("username"),
        vehicle_id=row["id"]
    )

    return {"message": "Vehicle deleted"}


@router.get("/vehicles")
def list_own_vehicles(user=Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    log_event("INFO", event="vehicle_list_own", username=user.get("username"))

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

    return [dict(r) for r in rows]


@router.get("/vehicles/{user_name}")
def list_user_vehicles(user_name: str, admin=Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    log_event("INFO", event="vehicle_list_admin", target_user=user_name)

    uid = get_user_id_by_username(con, user_name)
    if not uid:
        log_event("WARNING", event="vehicle_list_admin_failed",
                  reason="user_not_found", target_user=user_name)
        raise HTTPException(404, detail="User not found")

    rows = con.execute(
        """
        SELECT v.* FROM vehicles v
        JOIN user_vehicles uv ON v.id = uv.vehicle_id
        WHERE uv.user_id = ?
        """,
        (uid,)
    ).fetchall()

    return {_mk_lid(v["license_plate"]): dict(v) for v in rows}
