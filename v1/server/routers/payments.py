from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

from v1.server.deps import require_session, require_admin
from storage_utils import load_payment_data, save_payment_data
import session_calculator as sc

router = APIRouter()

#pydantic model voor de request body type
class PaymentIn(BaseModel):
    transaction: Optional[str] = None
    amount: Optional[float] = None
    coupled_to: Optional[str] = None
    t_data: Optional[Dict[str, Any]] = None
    validation: Optional[str] = None

@router.post("/payments")
def create_payment(payload: PaymentIn, user = Depends(require_session)):
    #security check voor transaction
    if payload.transaction is None or payload.transaction == "":
        raise HTTPException(400, detail={"error": "Required field missing", "field": "transaction"})
    if payload.amount is None:
        raise HTTPException(400, detail={"error": "Required field missing", "field": "amount"})

    payments = load_payment_data()
    payment = {
        "transaction": payload.transaction,
        "amount": payload.amount or 0,
        "initiator": user["username"],
        "created_at": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
        "completed": False,
        "hash": sc.generate_transaction_validation_hash()
    }
    payments.append(payment)
    save_payment_data(payments)
    return {"status": "Success", "payment": payment}

@router.post("/payments/refund")
def refund_payment(payload: PaymentIn, admin = Depends(require_admin)):
    if payload.amount is None:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "amount"})
    payments = load_payment_data()
    payment = {
        "transaction": payload.transaction or sc.generate_payment_hash(admin["username"], str(datetime.now())),
        "amount": -abs(payload.amount),
        "coupled_to": payload.coupled_to,
        "processed_by": admin["username"],
        "created_at": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
        "completed": False,
        "hash": sc.generate_transaction_validation_hash()
    }
    payments.append(payment)
    save_payment_data(payments)
    return {"status": "Success", "payment": payment}

@router.put("/payments/{pid}")
def complete_payment(pid: str, payload: PaymentIn, user = Depends(require_session)):
    payments = load_payment_data()
    payment = next((p for p in payments if p["transaction"] == pid), None)
    if not payment:
        raise HTTPException(404, detail="Payment not found")
    if payload.t_data is None or payload.validation is None:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "t_data/validation"})
    if payment["hash"] != payload.validation:
        raise HTTPException(401, detail={"error": "Validation failed", "info": "Security hash mismatch"})
    payment["completed"] = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    payment["t_data"] = payload.t_data
    save_payment_data(payments)
    return {"status": "Success", "payment": payment}

@router.get("/payments")
def list_my_payments(user = Depends(require_session)):
    results = []
    for p in load_payment_data():
        if p["initiator"] == user["username"] or p["processed_by"] == user["username"]:
            results.append(p)
    return results

@router.get("/payments/{user_name}")
def list_user_payments(user_name: str, admin = Depends(require_admin)):
    results = []
    for p in load_payment_data():
        if p["initiator"] == user_name or p["processed_by"] == user_name:
            results.append(p)
    return results

@router.get("/billing")
def my_billing(user = Depends(require_session)):
    data = []
    #We import here to avoid a circular import
    from storage_utils import load_parking_lot_data, load_json
    for pid, parkinglot in load_parking_lot_data().items():
        sessions = load_json(f"data/pdata/p{pid}-sessions.json") or {}
        for sid, session in sessions.items():
            if session["user"] == user["username"]:
                amount, hours, days = sc.calculate_price(parkinglot, sid, session)
                transaction = sc.generate_payment_hash(sid, session)
                payed = sc.check_payment_amount(transaction)
                data.append({
                    "session": {k: v for k, v in session.items() if k in ["licenseplate", "started", "stopped"]} | {"hours": hours, "days": days},
                    "parking": {k: v for k, v in parkinglot.items() if k in ["name", "location", "tariff", "daytariff"]},
                    "amount": amount,
                    "thash": transaction,
                    "payed": payed,
                    "balance": amount - payed
                })
    return data

@router.get("/billing/{user_name}") #admin only
def user_billing(user_name: str, admin = Depends(require_admin)):
    data = []
    from storage_utils import load_parking_lot_data, load_json
    for pid, parkinglot in load_parking_lot_data().items():
        sessions = load_json(f"data/pdata/p{pid}-sessions.json") or {}
        for sid, session in sessions.items():
            if session["user"] == user_name:
                amount, hours, days = sc.calculate_price(parkinglot, sid, session)
                transaction = sc.generate_payment_hash(sid, session)
                payed = sc.check_payment_amount(transaction)
                data.append({
                    "session": {k: v for k, v in session.items() if k in ["licenseplate", "started", "stopped"]} | {"hours": hours, "days": days},
                    "parking": {k: v for k, v in parkinglot.items() if k in ["name", "location", "tariff", "daytariff"]},
                    "amount": amount,
                    "thash": transaction,
                    "payed": payed,
                    "balance": amount - payed
                })
    return data
