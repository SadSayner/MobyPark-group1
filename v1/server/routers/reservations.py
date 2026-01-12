from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from ..deps import require_session, require_admin
from ...Database.database_logic import (
    get_db,
    get_parking_lot_by_id,
    update_reservation,
    delete_reservation
)
from logging_config import log_event
import sqlite3
from datetime import datetime

router = APIRouter()


class ReservationIn(BaseModel):
    parking_lot_id: int
    vehicle_id: int
    start_time: str
    duration: int
    status: Optional[str] = "pending"


class UpdateReservationIn(BaseModel):
    parking_lot_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    start_time: Optional[str] = None
    duration: Optional[int] = None
    status: Optional[str] = None


@router.post("/reservations")
def create_reservation(payload: ReservationIn, user=Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    from ...Database.database_logic import get_user_id_by_username

    log_event(
        level="INFO",
        event="reservation_create_attempt",
        username=user.get("username"),
        parking_lot_id=payload.parking_lot_id,
    )

    user_id = get_user_id_by_username(con, user.get("username"))
    if not user_id:
        log_event(
            level="ERROR",
            event="reservation_create_failed",
            reason="user_not_found",
        )
        raise HTTPException(400, detail="User not found")

    parkinglot = get_parking_lot_by_id(con, payload.parking_lot_id)
    if not parkinglot:
        log_event(
            level="WARNING",
            event="reservation_create_failed",
            parking_lot_id=payload.parking_lot_id,
            reason="parking_lot_not_found",
        )
        raise HTTPException(404, detail="Parking lot not found")

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur = con.execute(
        """
        INSERT INTO reservations (user_id, parking_lot_id, vehicle_id, start_time, duration, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            payload.parking_lot_id,
            payload.vehicle_id,
            payload.start_time,
            payload.duration,
            payload.status,
            created_at,
        ),
    )
    con.commit()
    rid = cur.lastrowid

    log_event(
        level="INFO",
        event="reservation_create_success",
        reservation_id=rid,
        username=user.get("username"),
    )

    return {
        "id": rid,
        "user_id": user_id,
        "parking_lot_id": payload.parking_lot_id,
        "vehicle_id": payload.vehicle_id,
        "start_time": payload.start_time,
        "duration": payload.duration,
        "status": payload.status,
        "created_at": created_at,
    }


@router.get("/reservations")
def list_reservations(user=Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    from ...Database.database_logic import get_user_id_by_username

    user_id = get_user_id_by_username(con, user.get("username"))
    if not user_id:
        log_event(
            level="WARNING",
            event="reservation_list_failed",
            reason="user_not_found",
        )
        return []

    log_event(
        level="INFO",
        event="reservation_list",
        username=user.get("username"),
    )

    rows = con.execute(
        "SELECT * FROM reservations WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()

    return [dict(row) for row in rows]


@router.get("/reservations/{rid}")
def get_reservation(rid: str, user=Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    from ...Database.database_logic import get_user_id_by_username

    log_event(
        level="INFO",
        event="reservation_get_attempt",
        reservation_id=rid,
        username=user.get("username"),
    )

    user_id = get_user_id_by_username(con, user.get("username"))

    row = con.execute(
        "SELECT * FROM reservations WHERE id = ?", (rid,)
    ).fetchone()
    if not row:
        log_event(
            level="WARNING",
            event="reservation_get_failed",
            reservation_id=rid,
            reason="not_found",
        )
        raise HTTPException(404, detail="Reservation not found")

    r = dict(row)
    if user.get("role") != "ADMIN" and r.get("user_id") != user_id:
        log_event(
            level="WARNING",
            event="reservation_get_failed",
            reservation_id=rid,
            reason="access_denied",
        )
        raise HTTPException(403, detail="Access denied")

    log_event(
        level="INFO",
        event="reservation_get_success",
        reservation_id=rid,
    )

    return r


@router.put("/reservations/{rid}")
def update_reservation_route(rid: str, payload: UpdateReservationIn, user=Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    from ...Database.database_logic import get_user_id_by_username

    log_event(
        level="INFO",
        event="reservation_update_attempt",
        reservation_id=rid,
        username=user.get("username"),
    )

    user_id = get_user_id_by_username(con, user.get("username"))

    row = con.execute(
        "SELECT * FROM reservations WHERE id = ?", (rid,)
    ).fetchone()
    if not row:
        log_event(
            level="WARNING",
            event="reservation_update_failed",
            reservation_id=rid,
            reason="not_found",
        )
        raise HTTPException(404, detail="Reservation not found")

    r = dict(row)
    if user.get("role") != "ADMIN" and r.get("user_id") != user_id:
        log_event(
            level="WARNING",
            event="reservation_update_failed",
            reservation_id=rid,
            reason="access_denied",
        )
        raise HTTPException(403, detail="Access denied")

    updates = []
    params = []

    for field, value in payload.model_dump(exclude_none=True).items():
        updates.append(f"{field} = ?")
        params.append(value)

    if updates:
        params.append(rid)
        sql = f"UPDATE reservations SET {', '.join(updates)} WHERE id = ?"
        con.execute(sql, params)
        con.commit()

    log_event(
        level="INFO",
        event="reservation_update_success",
        reservation_id=rid,
        fields=list(payload.model_dump(exclude_none=True).keys()),
    )

    updated = con.execute(
        "SELECT * FROM reservations WHERE id = ?", (rid,)
    ).fetchone()
    return dict(updated)


@router.delete("/reservations/{rid}")
def delete_reservation_route(rid: str, user=Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    from ...Database.database_logic import get_user_id_by_username

    log_event(
        level="INFO",
        event="reservation_delete_attempt",
        reservation_id=rid,
        username=user.get("username"),
    )

    user_id = get_user_id_by_username(con, user.get("username"))

    row = con.execute(
        "SELECT * FROM reservations WHERE id = ?", (rid,)
    ).fetchone()
    if not row:
        log_event(
            level="WARNING",
            event="reservation_delete_failed",
            reservation_id=rid,
            reason="not_found",
        )
        raise HTTPException(404, detail="Reservation not found")

    r = dict(row)
    if user.get("role") != "ADMIN" and r.get("user_id") != user_id:
        log_event(
            level="WARNING",
            event="reservation_delete_failed",
            reservation_id=rid,
            reason="access_denied",
        )
        raise HTTPException(403, detail="Access denied")

    con.execute("DELETE FROM reservations WHERE id = ?", (rid,))
    con.commit()

    log_event(
        level="INFO",
        event="reservation_delete_success",
        reservation_id=rid,
    )

    return {"message": "Reservation deleted"}
