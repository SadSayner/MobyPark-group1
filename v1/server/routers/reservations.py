from fastapi import APIRouter, HTTPException, Depends, Query, Response
from pydantic import BaseModel
from typing import Optional, Literal
from ..deps import require_session
from ...Database.database_logic import get_db, get_parking_lot_by_id, get_user_id_by_username
import csv
import io
import sqlite3
from datetime import datetime

router = APIRouter()


def _previous_month_year(now: datetime) -> tuple[int, int]:
    if now.month == 1:
        return 12, now.year - 1
    return now.month - 1, now.year

@router.get("/reservations/monthly_overview", summary="Get monthly parking overview as CSV", tags=["reservations"])
def monthly_overview(
    month: int | None = Query(None, ge=1, le=12, description="Month number (1-12). Only previous month is allowed."),
    year: int | None = Query(None, description="Year. Only previous month/year is allowed."),
    format: Literal["csv", "json"] = Query("csv", description="Response format: csv or json"),
    user = Depends(require_session),
    con: sqlite3.Connection = Depends(get_db)
):
    """
    Returns a CSV table of all parking actions (including free) for the given month and year, with a total cost.
    """
    last_month, last_year = _previous_month_year(datetime.now())

    # Enforce "past month" only.
    if month is None:
        month = last_month
    if year is None:
        year = last_year

    if month != last_month or year != last_year:
        raise HTTPException(
            400,
            detail=f"Only the previous month is allowed (month={last_month}, year={last_year})",
        )
    user_id = get_user_id_by_username(con, user.get("username"))
    if not user_id:
        raise HTTPException(400, detail="User not found")
    # Get all reservations for user
    rows = con.execute(
        "SELECT * FROM reservations WHERE user_id = ? AND strftime('%m', start_time) = ? AND strftime('%Y', start_time) = ? ORDER BY start_time ASC",
        (user_id, f"{month:02d}", str(year))
    ).fetchall()
    # Get costs for each reservation (if available)
    # If cost is not present, treat as 0 (free)
    if format == "json":
        total = 0.0
        items = []
        for row in rows:
            r = dict(row)
            cost = r.get("cost", 0.0)
            try:
                cost = float(cost) if cost is not None else 0.0
            except Exception:
                cost = 0.0
            r["cost"] = cost
            total += cost
            items.append(r)
        return {"month": month, "year": year, "total": total, "items": items}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "parking_lot_id", "vehicle_id", "start_time", "duration", "status", "cost"])
    total = 0.0
    for row in rows:
        cost = row["cost"] if "cost" in row.keys() and row["cost"] is not None else 0.0
        try:
            cost = float(cost)
        except Exception:
            cost = 0.0
        total += cost
        writer.writerow([
            row["id"], row["parking_lot_id"], row["vehicle_id"], row["start_time"], row["duration"], row["status"], cost
        ])
    writer.writerow([])
    writer.writerow(["Totaal", "", "", "", "", "", total])
    csv_data = output.getvalue()
    output.close()
    filename = f"monthly_overview_{year}_{month:02d}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


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
def create_reservation(payload: ReservationIn, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    from ...Database.database_logic import get_user_id_by_username
    from datetime import datetime

    #Get user ID
    user_id = get_user_id_by_username(con, user.get("username"))
    if not user_id:
        raise HTTPException(400, detail="User not found")

    #Check if parking lot exists
    parkinglot = get_parking_lot_by_id(con, payload.parking_lot_id)
    if not parkinglot:
        raise HTTPException(404, detail="Parking lot not found")

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Insert reservation using database schema
    cur = con.execute(
        """
        INSERT INTO reservations (user_id, parking_lot_id, vehicle_id, start_time, duration, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, payload.parking_lot_id, payload.vehicle_id, payload.start_time,
         payload.duration, payload.status, created_at),
    )
    con.commit()
    rid = cur.lastrowid

    return {
        "id": rid,
        "user_id": user_id,
        "parking_lot_id": payload.parking_lot_id,
        "vehicle_id": payload.vehicle_id,
        "start_time": payload.start_time,
        "duration": payload.duration,
        "status": payload.status,
        "created_at": created_at
    }


@router.get("/reservations")
def list_reservations(user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    """List all reservations for the current user"""
    from ...Database.database_logic import get_user_id_by_username

    user_id = get_user_id_by_username(con, user.get("username"))
    if not user_id:
        return []

    rows = con.execute(
        "SELECT * FROM reservations WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()

    return [dict(row) for row in rows]

@router.get("/reservations/{rid}")
def get_reservation(rid: str, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    from ...Database.database_logic import get_user_id_by_username

    user_id = get_user_id_by_username(con, user.get("username"))

    row = con.execute("SELECT * FROM reservations WHERE id = ?", (rid,)).fetchone()
    if not row:
        raise HTTPException(404, detail="Reservation not found")

    r = dict(row)
    #check admin
    if user.get("role") != "ADMIN" and r.get("user_id") != user_id:
        raise HTTPException(403, detail="Access denied")

    return r


@router.put("/reservations/{rid}")
def update_reservation_route(rid: str, payload: UpdateReservationIn, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    from ...Database.database_logic import get_user_id_by_username

    user_id = get_user_id_by_username(con, user.get("username"))

    row = con.execute("SELECT * FROM reservations WHERE id = ?", (rid,)).fetchone()
    if not row:
        raise HTTPException(404, detail="Reservation not found")

    r = dict(row)
    # Check ownership
    if user.get("role") != "ADMIN" and r.get("user_id") != user_id:
        raise HTTPException(403, detail="Access denied")

    # Build update query dynamically for provided fields
    updates = []
    params = []
    if payload.parking_lot_id is not None:
        updates.append("parking_lot_id = ?")
        params.append(payload.parking_lot_id)
    if payload.vehicle_id is not None:
        updates.append("vehicle_id = ?")
        params.append(payload.vehicle_id)
    if payload.start_time is not None:
        updates.append("start_time = ?")
        params.append(payload.start_time)
    if payload.duration is not None:
        updates.append("duration = ?")
        params.append(payload.duration)
    if payload.status is not None:
        updates.append("status = ?")
        params.append(payload.status)

    if updates:
        params.append(rid)
        sql = f"UPDATE reservations SET {', '.join(updates)} WHERE id = ?"
        con.execute(sql, params)
        con.commit()

    updated = con.execute("SELECT * FROM reservations WHERE id = ?", (rid,)).fetchone()
    return dict(updated)


@router.delete("/reservations/{rid}")
def delete_reservation_route(rid: str, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    from ...Database.database_logic import get_user_id_by_username

    user_id = get_user_id_by_username(con, user.get("username"))

    row = con.execute("SELECT * FROM reservations WHERE id = ?", (rid,)).fetchone()
    if not row:
        raise HTTPException(404, detail="Reservation not found")

    r = dict(row)
    # Check ownership
    if user.get("role") != "ADMIN" and r.get("user_id") != user_id:
        raise HTTPException(403, detail="Access denied")

    # Delete reservation
    con.execute("DELETE FROM reservations WHERE id = ?", (rid,))
    con.commit()

    return {"message": "Reservation deleted"}