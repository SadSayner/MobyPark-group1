from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from v1.server.deps import require_session, require_admin
from storage_utils import load_reservation_data, save_reservation_data, load_parking_lot_data, save_parking_lot_data

router = APIRouter()

class ReservationIn(BaseModel):
    licenseplate: str
    startdate: str
    enddate: str
    parkinglot: str
    user: Optional[str] = None

@router.post("/reservations")
def create_reservation(payload: ReservationIn, user = Depends(require_session)):
    reservations = load_reservation_data()
    parking_lots = load_parking_lot_data()

    if payload.licenseplate in (None, ""):
        raise HTTPException(400, detail={"error": "Require field missing", "field": "licenseplate"})
    if payload.startdate in (None, ""):
        raise HTTPException(400, detail={"error": "Require field missing", "field": "startdate"})
    if payload.enddate in (None, ""):
        raise HTTPException(400, detail={"error": "Require field missing", "field": "enddate"})
    if payload.parkinglot in (None, ""):
        raise HTTPException(400, detail={"error": "Require field missing", "field": "parkinglot"})
    if payload.parkinglot not in parking_lots:
        raise HTTPException(404, detail={"error": "Parking lot not found", "field": "parkinglot"})
 
    rid = str(len(reservations) + 1)
    data = payload.model_dump()
    if user["role"] != "ADMIN":
        data["user"] = user["username"]
    elif not data["user"]:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "user"})
    reservations[rid] = data
    data["id"] = rid
    parking_lots[data["parkinglot"]]["reserved"] += 1
    save_reservation_data(reservations)
    save_parking_lot_data(parking_lots)
    return {"status": "Success", "reservation": data}

@router.get("/reservations/{rid}")
def get_reservation(rid: str, user = Depends(require_session)):
    reservations = load_reservation_data()
    if rid not in reservations:
        raise HTTPException(404, detail="Reservation not found")
    r = reservations[rid]
    if user["role"] != "ADMIN" and r["user"] != user["username"]:
        raise HTTPException(403, detail="Access denied")
    return r

@router.put("/reservations/{rid}")
def update_reservation(rid: str, payload: ReservationIn, user = Depends(require_session)):
    reservations = load_reservation_data()
    if rid not in reservations:
        raise HTTPException(404, detail="Reservation not found")
    data = payload.model_dump()

    if payload.licenseplate in (None, ""):
        raise HTTPException(400, detail={"error": "Require field missing", "field": "licenseplate"})
    if payload.startdate in (None, ""):
        raise HTTPException(400, detail={"error": "Require field missing", "field": "startdate"})
    if payload.enddate in (None, ""):
        raise HTTPException(400, detail={"error": "Require field missing", "field": "enddate"})
    if payload.parkinglot in (None, ""):
        raise HTTPException(400, detail={"error": "Require field missing", "field": "parkinglot"})
  
    if user["role"] != "ADMIN":
        data["user"] = user["username"]
    elif not data["user"]:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "user"})
    reservations[rid] = data
    save_reservation_data(reservations)
    return {"status": "Updated", "reservation": data}

@router.delete("/reservations/{rid}")
def delete_reservation(rid: str, user = Depends(require_session)):
    reservations = load_reservation_data()
    parking_lots = load_parking_lot_data()
    if rid not in reservations:
        raise HTTPException(404, detail="Reservation not found")
    owner = reservations[rid]["user"]
    if user["role"] != "ADMIN" and owner != user["username"]:
        raise HTTPException(403, detail="Access denied")
    pid = reservations[rid]["parkinglot"]
    del reservations[rid]
    parking_lots[pid]["reserved"] -= 1
    save_reservation_data(reservations)
    save_parking_lot_data(parking_lots)
    return {"status": "Deleted"}
