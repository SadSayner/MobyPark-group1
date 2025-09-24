
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

from server.deps import require_session, require_admin
from storage_utils import load_json, save_data, load_json as load

router = APIRouter()

def now_str() -> str:
    return datetime.now().strftime("%d-%m-%Y %H:%M:%S")

class VehicleIn(BaseModel):
    name: str
    license_plate: Optional[str] = None

@router.post("/vehicles")
def create_vehicle(payload: VehicleIn, user = Depends(require_session)):
    vehicles = load_json("data/vehicles.json") or {}
    uvehicles = vehicles.get(user["username"], {})
    for field in ["name", "license_plate"]:
        if getattr(payload, field, None) in (None, ""):
            raise HTTPException(400, detail={"error": "Require field missing", "field": field})
    lid = payload.license_plate.replace("-", "")
    if lid in uvehicles:
        raise HTTPException(400, detail={"error": "Vehicle already exists", "data": uvehicles.get(lid)})
    if not uvehicles:
        vehicles[user["username"]] = {}
    vehicles[user["username"]][lid] = {
        "licenseplate": payload.license_plate,
        "name": payload.name,
        "created_at": now_str(),
        "updated_at": now_str(),
    }
    save_data("data/vehicles.json", vehicles)
    return {"status": "Success", "vehicle": payload.model_dump()}

@router.put("/vehicles/{lid}")
def update_vehicle(lid: str, payload: VehicleIn, user = Depends(require_session)):
    vehicles = load_json("data/vehicles.json") or {}
    uvehicles = vehicles.get(user["username"], {})
    if not payload.name:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "name"})
    if not uvehicles:
        vehicles[user["username"]] = {}
    if lid not in uvehicles:
        vehicles[user["username"]][lid] = {
            "licenseplate": payload.license_plate,
            "name": payload.name,
            "created_at": now_str(),
            "updated_at": now_str(),
        }
    vehicles[user["username"]][lid]["name"] = payload.name
    vehicles[user["username"]][lid]["updated_at"] = now_str()
    save_data("data/vehicles.json", vehicles)
    return {"status": "Success", "vehicle": vehicles[user["username"]][lid]}

@router.delete("/vehicles/{lid}")
def delete_vehicle(lid: str, user = Depends(require_session)):
    vehicles = load_json("data/vehicles.json") or {}
    uvehicles = vehicles.get(user["username"], {})
    if lid not in uvehicles:
        raise HTTPException(404, detail="Vehicle not found")
    del vehicles[user["username"]][lid]
    save_data("data/vehicles.json", vehicles)
    return {"status": "Deleted"}

@router.get("/vehicles")
def list_own_vehicles(user = Depends(require_session)):
    vehicles = load_json("data/vehicles.json") or {}
    return vehicles.get(user["username"], {})

@router.get("/vehicles/{user_name}")
def list_user_vehicles(user_name: str, admin = Depends(require_admin)):
    vehicles = load_json("data/vehicles.json") or {}
    users = load_json("data/users.json") or []
    if user_name not in [u.get("username") for u in users]:
        raise HTTPException(404, detail="User not found")
    return vehicles.get(user_name, {})

@router.post("/vehicles/{lid}/entry")
def vehicle_entry(lid: str, data: Dict[str, Any] = Body(...), user = Depends(require_session)):
    if "parkinglot" not in data:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "parkinglot"})
    vehicles = load_json("data/vehicles.json") or {}
    uvehicles = vehicles.get(user["username"], {})
    if lid not in uvehicles:
        raise HTTPException(400, detail={"error": "Vehicle does not exist", "data": lid})
    return {"status": "Accepted", "vehicle": uvehicles[lid]}

@router.get("/vehicles/{vid}/reservations")
def vehicle_reservations(vid: str, user = Depends(require_session)):
    vehicles = load_json("data/vehicles.json") or {}
    if vid not in (vehicles.get(user["username"], {}) or {}):
        raise HTTPException(404, detail="Not found")
    return []

@router.get("/vehicles/{vid}/history")
def vehicle_history(vid: str, user = Depends(require_session)):
    vehicles = load_json("data/vehicles.json") or {}
    if vid not in (vehicles.get(user["username"], {}) or {}):
        raise HTTPException(404, detail="Not found")
    return []
