from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from v1.server.deps import require_session, require_admin
from v1.Database.database_logic import get_db
import sqlite3

router = APIRouter()


class ReservationIn(BaseModel):
    licenseplate: str
    startdate: str
    enddate: str
    parkinglot: str
    user: Optional[str] = None


@router.post("/reservations")
def create_reservation(payload: ReservationIn, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):

    if not payload.licenseplate:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "licenseplate"})
    if not payload.startdate:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "startdate"})
    if not payload.enddate:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "enddate"})
    if not payload.parkinglot:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "parkinglot"})

    #kijk of parking lot bestaat
    parkinglot = con.execute("SELECT id FROM parking_lots WHERE id = ?", (payload.parkinglot,)).fetchone()
    if not parkinglot:
        raise HTTPException(404, detail={"error": "Parking lot not found", "field": "parkinglot"})

    data = payload.model_dump()
    if user.get("role") != "ADMIN":
        data["user"] = user.get("username")
    else:
        if not data.get("user"):
            raise HTTPException(400, detail={"error": "Require field missing", "field": "user"})

    # insert reservation
    cur = con.execute(
        """
        INSERT INTO reservations (licenseplate, startdate, enddate, parkinglot, user)
        VALUES (?, ?, ?, ?, ?)
        """,
        (data["licenseplate"], data["startdate"], data["enddate"], data["parkinglot"], data["user"]),
    )
    con.commit()
    rid = cur.lastrowid

    # increment reserved count on parking_lots
    con.execute(
        "UPDATE parking_lots SET reserved = COALESCE(reserved,0) + 1 WHERE id = ?",
        (data["parkinglot"],),
    )
    con.commit()

    data["id"] = str(rid)
    return {"status": "Success", "reservation": data}


@router.get("/reservations/{rid}")
def get_reservation(rid: str, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    row = con.execute("SELECT * FROM reservations WHERE id = ?", (rid,)).fetchone()
    if not row:
        raise HTTPException(404, detail="Reservation not found")
    r = dict(row)
    if user.get("role") != "ADMIN" and r.get("user") != user.get("username"):
        raise HTTPException(403, detail="Access denied")
    # ensure id is a string (matching previous behaviour)
    r["id"] = str(r.get("id"))
    return r


@router.put("/reservations/{rid}")
def update_reservation(rid: str, payload: ReservationIn, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    row = con.execute("SELECT * FROM reservations WHERE id = ?", (rid,)).fetchone()
    if not row:
        raise HTTPException(404, detail="Reservation not found")

    # validate incoming fields
    if not payload.licenseplate:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "licenseplate"})
    if not payload.startdate:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "startdate"})
    if not payload.enddate:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "enddate"})
    if not payload.parkinglot:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "parkinglot"})

    # authorization / user assignment
    data = payload.model_dump()
    if user.get("role") != "ADMIN":
        data["user"] = user.get("username")
    else:
        if not data.get("user"):
            raise HTTPException(400, detail={"error": "Require field missing", "field": "user"})

    # handle possible parkinglot change: adjust reserved counters
    old = dict(row)
    old_parkinglot = old.get("parkinglot")
    new_parkinglot = data["parkinglot"]
    if old_parkinglot != new_parkinglot:
        # ensure new parking lot exists
        pl = con.execute("SELECT id FROM parking_lots WHERE id = ?", (new_parkinglot,)).fetchone()
        if not pl:
            raise HTTPException(404, detail={"error": "Parking lot not found", "field": "parkinglot"})
        # decrement old
        if old_parkinglot:
            con.execute("UPDATE parking_lots SET reserved = MAX(COALESCE(reserved,0) - 1, 0) WHERE id = ?", (old_parkinglot,))
        # increment new
        con.execute("UPDATE parking_lots SET reserved = COALESCE(reserved,0) + 1 WHERE id = ?", (new_parkinglot,))

    # perform update
    con.execute(
        """
        UPDATE reservations
        SET licenseplate = ?, startdate = ?, enddate = ?, parkinglot = ?, user = ?
        WHERE id = ?
        """,
        (data["licenseplate"], data["startdate"], data["enddate"], data["parkinglot"], data["user"], rid),
    )
    con.commit()

    updated = con.execute("SELECT * FROM reservations WHERE id = ?", (rid,)).fetchone()
    result = dict(updated)
    result["id"] = str(result.get("id"))
    return {"status": "Updated", "reservation": result}


@router.delete("/reservations/{rid}")
def delete_reservation(rid: str, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    row = con.execute("SELECT * FROM reservations WHERE id = ?", (rid,)).fetchone()
    if not row:
        raise HTTPException(404, detail="Reservation not found")
    owner = row.get("user")
    if user.get("role") != "ADMIN" and owner != user.get("username"):
        raise HTTPException(403, detail="Access denied")

    pid = row.get("parkinglot")
    con.execute("DELETE FROM reservations WHERE id = ?", (rid,))
    if pid:
        con.execute("UPDATE parking_lots SET reserved = MAX(COALESCE(reserved,0) - 1, 0) WHERE id = ?", (pid,))
    con.commit()
    return {"status": "Deleted"}