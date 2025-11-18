from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import sqlite3

from v1.server.deps import require_session, require_admin
from storage_utils import load_payment_data, save_payment_data
import session_calculator as sc
from v1.Database.database_logic import get_db

router = APIRouter()

#pydantic model voor de request body type
class PaymentIn(BaseModel):
    transaction: Optional[str] = None
    amount: float = Field(..., gt=0)         # required and must be > 0
    parkingsession_id: Optional[str] = None
    t_data: Optional[Dict[str, Any]] = None
    validation: Optional[str] = None
    recipient: Optional[str] = None

    class Config:
        extra = "forbid"                     # reject unknown fields

def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}

@router.post("/payments")
def create_payment(payload: PaymentIn, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    try:
        amount = float(payload.amount)
    except Exception:
        raise HTTPException(400, detail={"error": "Invalid amount"})
    if amount <= 0:
        raise HTTPException(400, detail={"error": "Invalid amount"})

    cur = con.execute("SELECT id FROM users WHERE username = ?", (user.get("username"),))
    row = cur.fetchone()
    if not row:
        raise HTTPException(400, detail="User not found")
    user_id = row["id"]

    # optional: link parking session (id) to created payment. Only if the user owns the session or is admin.
    session_id = None
    parking_lot_id = None
    if payload.parkingsession_id:
        try:
            linked_sid = int(payload.parkingsession_id)
        except Exception:
            raise HTTPException(400, detail="Invalid parkingsession_id (expect parking session id)")
        srow = con.execute("SELECT id, user_id, parking_lot_id FROM parking_sessions WHERE id = ?", (linked_sid,)).fetchone()
        if not srow:
            raise HTTPException(404, detail="Linked parking session not found")
        # only owner or admin may create payment for the session
        if user.get("role") != "ADMIN" and srow["user_id"] is not None and srow["user_id"] != user_id:
            raise HTTPException(403, detail="Not allowed to create payment for this session")
        session_id = srow["id"]
        parking_lot_id = srow["parking_lot_id"]

    # generate transaction id and validation hash
    import uuid
    transaction_id = payload.transaction if payload.transaction else str(uuid.uuid4())
    validation_hash = sc.generate_transaction_validation_hash()
    created_at = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    if isinstance(payload.t_data, dict):
        # use the explicit provider fields when present, fall back to common synonyms
        t_date = payload.t_data.get("t_date") or payload.t_data.get("date") or created_at
        t_method = payload.t_data.get("t_method") or payload.t_data.get("method") or "unknown"
        t_issuer = payload.t_data.get("t_issuer") or payload.t_data.get("issuer") or ""
        t_bank = payload.t_data.get("t_bank") or payload.t_data.get("bank") or ""
    else:
        # sensible, human-readable defaults
        t_date = created_at
        t_method = "pending"
        t_issuer = ""
        t_bank = ""

    # persist to DB
    con.execute("""
        INSERT INTO payments (
            transaction_id, amount, user_id, session_id, parking_lot_id,
            created_at, completed, hash, t_date, t_method, t_issuer, t_bank
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        transaction_id,
        amount,
        user_id,
        session_id,
        parking_lot_id,
        created_at,
        0,                 #verwacht een int(idk waarom), 0 = false
        validation_hash,
        t_date,
        t_method,
        t_issuer, 
        t_bank,
    ))
    con.commit()

    payment_record = {
        "transaction": transaction_id,
        "amount": amount,
        "user": user.get("username"),
        "user_id": user_id,
        "session_id": session_id,
        "parking_lot_id": parking_lot_id,
        "created_at": created_at,
        "completed": False,
        "hash": validation_hash
    }

    return {"status": "Success", "payment": payment_record}

@router.post("/payments/refund")
def refund_payment(payload: PaymentIn, admin = Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    try:
        amount = float(payload.amount)
    except Exception:
        raise HTTPException(400, detail={"error": "Invalid amount"})
    if amount <= 0:
        raise HTTPException(400, detail={"error": "amount must be greater than zero"})

    # get admin id (prefer id from require_admin if present)
    admin_id = admin.get("id")
    if admin_id is None:
        cur = con.execute("SELECT id FROM users WHERE username = ?", (admin.get("username"),))
        row = cur.fetchone()
        if not row:
            raise HTTPException(400, detail="Admin not found")
        admin_id = row["id"]

    # resolve linked session (if provided) and determine refund recipient
    session_id = None
    parking_lot_id = None
    recipient_user_id = None
    if payload.parkingsession_id:
        try:
            sid = int(payload.parkingsession_id)
        except Exception:
            raise HTTPException(400, detail="Invalid parkingsession_id (expect parking session id)")
        srow = con.execute("SELECT id, user_id, parking_lot_id FROM parking_sessions WHERE id = ?", (sid,)).fetchone()
        if not srow:
            raise HTTPException(404, detail="Linked parking session not found")
        session_id = srow["id"]
        parking_lot_id = srow["parking_lot_id"]
        recipient_user_id = srow["user_id"]  # may be None for guest sessions

    # if recipient not determined from session, require explicit recipient username
    if recipient_user_id is None:
        if not payload.recipient:
            raise HTTPException(400, detail="Refund must specify a recipient username or a session with an owner")
        cur = con.execute("SELECT id FROM users WHERE username = ?", (payload.recipient,))
        urow = cur.fetchone()
        if not urow:
            raise HTTPException(404, detail="Recipient user not found")
        recipient_user_id = urow["id"]

    # transaction metadata
    import uuid
    transaction_id = payload.transaction or str(uuid.uuid4())
    validation_hash = sc.generate_transaction_validation_hash()
    created_at = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    # simple provider fields mapping
    if isinstance(payload.t_data, dict):
        t_date = payload.t_data.get("t_date") or payload.t_data.get("date") or created_at
        t_method = payload.t_data.get("t_method") or payload.t_data.get("method") or "refund"
        t_issuer = payload.t_data.get("t_issuer") or payload.t_data.get("issuer") or ""
        t_bank = payload.t_data.get("t_bank") or payload.t_data.get("bank") or ""
        t_amount = payload.t_data.get("t_amount") or payload.t_data.get("amount")
    else:
        t_date = created_at
        t_method = "refund"
        t_issuer = ""
        t_bank = ""
        t_amount = None

    # insert refund row (negative amount); link to recipient_user_id (the refunded user)
    con.execute(
        """
        INSERT INTO payments (
            transaction_id, amount, user_id, session_id, parking_lot_id,
            created_at, completed, hash, t_date, t_method, t_issuer, t_bank
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            transaction_id,
            -abs(amount),
            recipient_user_id,
            session_id,
            parking_lot_id,
            created_at,
            1,                    # refunds considered completed
            validation_hash,
            t_date,
            t_method,
            t_issuer,
            t_bank,
        ),
    )
    con.commit()

    payment = {
        "transaction": transaction_id,
        "amount": -abs(amount),
        "processed_by": admin.get("username"),
        "user_id": recipient_user_id,
        "session_id": session_id,
        "parking_lot_id": parking_lot_id,
        "created_at": created_at,
        "completed": True,
        "hash": validation_hash,
        "t_date": t_date,
        "t_method": t_method,
        "t_issuer": t_issuer,
        "t_bank": t_bank,
        "t_amount": t_amount,
    }
    return {"status": "Success", "payment": payment}


@router.put("/payments/{transaction_id}")
def complete_payment(transaction_id: str, payload: PaymentIn, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    # find payment by transaction_id
    row = con.execute("SELECT * FROM payments WHERE transaction_id = ?", (transaction_id,)).fetchone()
    if not row:
        raise HTTPException(404, detail="Payment not found")

    # require provider data and validation hash
    if payload.t_data is None or payload.validation is None:
        raise HTTPException(400, detail={"error": "Require field missing", "field": "t_data/validation"})
    if row["hash"] != payload.validation:
        raise HTTPException(401, detail={"error": "Validation failed", "info": "Security hash mismatch"})

    if not isinstance(payload.t_data, dict):
        raise HTTPException(400, detail="t_data must be an object")


    t_date = payload.t_data.get("t_date") or payload.t_data.get("date") or datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    t_method = payload.t_data.get("t_method") or payload.t_data.get("method") or ""
    t_issuer = payload.t_data.get("t_issuer") or payload.t_data.get("issuer") or ""
    t_bank = payload.t_data.get("t_bank") or payload.t_data.get("bank") or ""
    t_amount = payload.t_data.get("t_amount") or payload.t_data.get("amount")

    # mark as completed (use int flag) and save provider fields
    completed = 1
    completed_at = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    con.execute(
        """
        UPDATE payments
        SET completed = ?, t_date = ?, t_method = ?, t_issuer = ?, t_bank = ?, t_amount = ?
        WHERE transaction_id = ?
        """,
        (completed, t_date, t_method, t_issuer, t_bank, t_amount, transaction_id)
    )
    con.commit()

    updated = con.execute("SELECT * FROM payments WHERE transaction_id = ?", (transaction_id,)).fetchone()
    return {"status": "Success", "payment_completed_at": completed_at, "payment": _row_to_dict(updated)}


@router.get("/payments")
def list_my_payments(user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute("SELECT id FROM users WHERE username = ?", (user.get("username"),))
    user_row = cur.fetchone()
    if not user_row:
        return []
    user_id = user_row["id"]
    rows = con.execute("SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    return [_row_to_dict(r) for r in rows]


@router.get("/payments/{user_name}")
def list_user_payments(user_name: str, admin = Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute("SELECT id FROM users WHERE username = ?", (user_name,))
    user_row = cur.fetchone()
    if not user_row:
        return []
    user_id = user_row["id"]
    rows = con.execute("SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    return [_row_to_dict(r) for r in rows]


@router.get("/billing")
def my_billing(user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    # build billing view from DB parking_sessions + parking_lots + payments
    cur = con.execute("SELECT id FROM users WHERE username = ?", (user.get("username"),))
    user_row = cur.fetchone()
    if not user_row:
        return []
    user_id = user_row["id"]

    sessions = con.execute("SELECT * FROM parking_sessions WHERE user_id = ?", (user_id,)).fetchall()
    data = []
    for s in sessions:
        sdict = dict(s)
        sid = sdict.get("id")
        lot_id = sdict.get("parking_lot_id")
        lot = con.execute("SELECT * FROM parking_lots WHERE id = ?", (lot_id,)).fetchone()
        lotd = dict(lot) if lot else {}
        parking = {
            "name": lotd.get("name"),
            "location": lotd.get("location"),
            "tariff": lotd.get("tariff"),
            "daytariff": lotd.get("daytariff"),
        }
        licenseplate = sdict.get("license_plate") or sdict.get("licenseplate") or sdict.get("license")
        session_obj = {
            "licenseplate": licenseplate,
            "started": sdict.get("started"),
            "stopped": sdict.get("stopped")
        }
        try:
            amount, hours, days = sc.calculate_price(parking, str(sid), session_obj)
        except Exception:
            amount, hours, days = 0, 0, 0
        paid_row = con.execute("SELECT COALESCE(SUM(amount),0) as paid FROM payments WHERE session_id = ?", (sid,)).fetchone()
        paid = paid_row["paid"] if paid_row else 0
        data.append({
            "session": {"licenseplate": licenseplate, "started": session_obj["started"], "stopped": session_obj["stopped"], "hours": hours, "days": days},
            "parking": parking,
            "amount": amount,
            "payed": paid,
            "balance": amount - paid
        })
    return data


@router.get("/billing/{user_name}")  # admin only
def user_billing(user_name: str, admin = Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute("SELECT id FROM users WHERE username = ?", (user_name,))
    urow = cur.fetchone()
    if not urow:
        return []
    uid = urow["id"]

    sessions = con.execute("SELECT * FROM parking_sessions WHERE user_id = ?", (uid,)).fetchall()
    data = []
    for s in sessions:
        sdict = dict(s)
        sid = sdict.get("id")
        lot_id = sdict.get("parking_lot_id")
        lot = con.execute("SELECT * FROM parking_lots WHERE id = ?", (lot_id,)).fetchone()
        lotd = dict(lot) if lot else {}
        parking = {
            "name": lotd.get("name"),
            "location": lotd.get("location"),
            "tariff": lotd.get("tariff"),
            "daytariff": lotd.get("daytariff"),
        }
        licenseplate = sdict.get("license_plate") or sdict.get("licenseplate") or sdict.get("license")
        session_obj = {"licenseplate": licenseplate, "started": sdict.get("started"), "stopped": sdict.get("stopped")}
        try:
            amount, hours, days = sc.calculate_price(parking, str(sid), session_obj)
        except Exception:
            amount, hours, days = 0, 0, 0
        paid_row = con.execute("SELECT COALESCE(SUM(amount),0) as paid FROM payments WHERE session_id = ?", (sid,)).fetchone()
        paid = paid_row["paid"] if paid_row else 0
        data.append({
            "session": {"licenseplate": licenseplate, "started": session_obj["started"], "stopped": session_obj["stopped"], "hours": hours, "days": days},
            "parking": parking,
            "amount": amount,
            "payed": paid,
            "balance": amount - paid
        })
    return data
