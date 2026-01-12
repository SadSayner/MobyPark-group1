from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import sqlite3

from ..deps import require_session, require_admin
from ...storage_utils import load_payment_data, save_payment_data
from ... import session_calculator as sc
from ...Database.database_logic import get_db, get_user_id_by_username, get_payments_by_user_id, update_payment
from logging_config import log_event

router = APIRouter()

# pydantic model voor de request body type


class PaymentIn(BaseModel):
    transaction: Optional[str] = None
    amount: float = Field(..., gt=0)         # required and must be > 0
    parkingsession_id: Optional[str] = None
    session_id: Optional[int] = None  # Accept session_id from tests
    payment_method: Optional[str] = None  # Accept payment_method from tests
    t_data: Optional[Dict[str, Any]] = None
    validation: Optional[str] = None
    recipient: Optional[str] = None

    class Config:
        extra = "allow"  # voor unknown fields


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@router.post("/payments")
def create_payment(payload: PaymentIn, user=Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    log_event(level="INFO", event="payment_create_attempt",
              username=user["username"], amount=payload.amount)
    try:
        amount = float(payload.amount)
    except Exception:
        log_event(level="WARNING", event="payment_create_failed",
                  username=user["username"], reason="invalid_amount_format")
        raise HTTPException(400, detail={"error": "Invalid amount"})
    if amount <= 0:
        log_event(level="WARNING", event="payment_create_failed",
                  username=user["username"], reason="amount_zero_or_negative")
        raise HTTPException(400, detail={"error": "Invalid amount"})

    # Use database function to get user ID
    user_id = get_user_id_by_username(con, user.get("username"))
    if not user_id:
        log_event(level="ERROR", event="payment_create_failed",
                  username=user["username"], reason="user_not_found_in_db")
        raise HTTPException(400, detail="User not found")

    # link parking session (id) to created payment. Only if the user owns the session or is admin.
    session_id = None
    parking_lot_id = None
    # Check both session_id and parkingsession_id for compatibility
    if payload.session_id or payload.parkingsession_id:
        try:
            linked_sid = int(
                payload.session_id if payload.session_id else payload.parkingsession_id)
        except Exception:
            log_event(level="WARNING", event="payment_create_failed",
                      username=user["username"], reason="invalid_session_id_format")
            raise HTTPException(
                400, detail="Invalid parkingsession_id (expect parking session id)")
        srow = con.execute(
            "SELECT session_id, user_id, parking_lot_id FROM sessions WHERE session_id = ?", (linked_sid,)).fetchone()
        if not srow:
            log_event(level="WARNING", event="payment_create_failed",
                      username=user["username"], reason="linked_session_not_found")
            raise HTTPException(404, detail="Linked parking session not found")
        # only owner or admin may create payment for the session
        if user.get("role") != "ADMIN" and srow["user_id"] is not None and srow["user_id"] != user_id:
            log_event(level="WARNING", event="payment_create_failed",
                      username=user["username"], reason="session_ownership_mismatch")
            raise HTTPException(
                403, detail="Not allowed to create payment for this session")
        session_id = srow["session_id"]
        parking_lot_id = srow["parking_lot_id"]

    # genereer transaction id en validation hash
    import uuid
    transaction_id = payload.transaction if payload.transaction else str(
        uuid.uuid4())
    validation_hash = sc.generate_transaction_validation_hash()
    created_at = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    if isinstance(payload.t_data, dict):
        # use the explicit provider fields when present
        t_date = payload.t_data.get(
            "t_date") or payload.t_data.get("date") or created_at
        t_method = payload.t_data.get(
            "t_method") or payload.t_data.get("method") or "unknown"
        t_issuer = payload.t_data.get(
            "t_issuer") or payload.t_data.get("issuer") or ""
        t_bank = payload.t_data.get(
            "t_bank") or payload.t_data.get("bank") or ""
    else:
        t_date = created_at
        t_method = "pending"
        t_issuer = ""
        t_bank = ""

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
        0,  # verwacht een int(idk waarom), 0 = false
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

    log_event(level="INFO", event="payment_create_success",
              username=user["username"], transaction_id=transaction_id)
    return {"status": "Success", "payment": payment_record}


@router.post("/payments/refund")
def refund_payment(payload: PaymentIn, admin=Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    log_event(level="INFO", event="payment_refund_attempt",
              admin=admin["username"], amount=payload.amount)
    try:
        amount = float(payload.amount)
    except Exception:
        log_event(level="WARNING", event="payment_refund_failed",
                  admin=admin["username"], reason="invalid_amount_format")
        raise HTTPException(400, detail={"error": "Invalid amount"})
    if amount <= 0:
        log_event(level="WARNING", event="payment_refund_failed",
                  admin=admin["username"], reason="amount_zero_or_negative")
        raise HTTPException(
            400, detail={"error": "amount must be greater than zero"})

    # fetch admin id (prefer id from require_admin if present)
    admin_id = admin.get("id")
    if admin_id is None:
        # Use database function to get admin ID
        admin_id = get_user_id_by_username(con, admin.get("username"))
        if not admin_id:
            log_event(level="ERROR", event="payment_refund_failed",
                      admin=admin["username"], reason="admin_not_found_in_db")
            raise HTTPException(400, detail="Admin not found")

    # resolve linked session (if provided) and determine refund recipient
    session_id = None
    parking_lot_id = None
    recipient_user_id = None
    if payload.parkingsession_id:
        try:
            sid = int(payload.parkingsession_id)
        except Exception:
            log_event(level="WARNING", event="payment_refund_failed",
                      admin=admin["username"], reason="invalid_session_id_format")
            raise HTTPException(
                400, detail="Invalid parkingsession_id (expect parking session id)")
        srow = con.execute(
            "SELECT session_id, user_id, parking_lot_id FROM sessions WHERE session_id = ?", (sid,)).fetchone()
        if not srow:
            log_event(level="WARNING", event="payment_refund_failed",
                      admin=admin["username"], reason="linked_session_not_found")
            raise HTTPException(404, detail="Linked parking session not found")
        session_id = srow["session_id"]
        parking_lot_id = srow["parking_lot_id"]
        recipient_user_id = srow["user_id"]  # may be None for guest sessions

    # if recipient not determined from session, require explicit recipient username
    if recipient_user_id is None:
        if not payload.recipient:
            log_event(level="WARNING", event="payment_refund_failed",
                      admin=admin["username"], reason="missing_recipient")
            raise HTTPException(
                400, detail="Refund must specify a recipient username or a session with an owner")
        # Use database function to get recipient ID
        recipient_user_id = get_user_id_by_username(con, payload.recipient)
        if not recipient_user_id:
            log_event(level="WARNING", event="payment_refund_failed",
                      admin=admin["username"], reason="recipient_not_found")
            raise HTTPException(404, detail="Recipient user not found")

    # transaction metadata
    import uuid
    transaction_id = payload.transaction or str(uuid.uuid4())
    validation_hash = sc.generate_transaction_validation_hash()
    created_at = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    # simple provider fields mapping
    if isinstance(payload.t_data, dict):
        t_date = payload.t_data.get(
            "t_date") or payload.t_data.get("date") or created_at
        t_method = payload.t_data.get(
            "t_method") or payload.t_data.get("method") or "refund"
        t_issuer = payload.t_data.get(
            "t_issuer") or payload.t_data.get("issuer") or ""
        t_bank = payload.t_data.get(
            "t_bank") or payload.t_data.get("bank") or ""
        t_amount = payload.t_data.get(
            "t_amount") or payload.t_data.get("amount")
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
    log_event(level="INFO", event="payment_refund_success",
              admin=admin["username"], transaction_id=transaction_id)
    return {"status": "Success", "payment": payment}


@router.put("/payments/{transaction_id}")
def complete_payment(transaction_id: str, payload: PaymentIn, user=Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    log_event(level="INFO", event="payment_complete_attempt",
              username=user["username"], transaction_id=transaction_id)
    # find payment by transaction_id
    row = con.execute(
        "SELECT * FROM payments WHERE transaction_id = ?", (transaction_id,)).fetchone()
    if not row:
        log_event(level="WARNING", event="payment_complete_failed",
                  username=user["username"], transaction_id=transaction_id, reason="not_found")
        raise HTTPException(404, detail="Payment not found")

    # require provider data and validation hash
    if payload.t_data is None or payload.validation is None:
        log_event(level="WARNING", event="payment_complete_failed",
                  username=user["username"], transaction_id=transaction_id, reason="missing_provider_data")
        raise HTTPException(
            400, detail={"error": "Require field missing", "field": "t_data/validation"})
    if row["hash"] != payload.validation:
        log_event(level="WARNING", event="payment_complete_failed",
                  username=user["username"], transaction_id=transaction_id, reason="hash_mismatch")
        raise HTTPException(
            401, detail={"error": "Validation failed", "info": "Security hash mismatch"})

    if not isinstance(payload.t_data, dict):
        log_event(level="WARNING", event="payment_complete_failed",
                  username=user["username"], transaction_id=transaction_id, reason="invalid_t_data_format")
        raise HTTPException(400, detail="t_data must be an object")

    t_date = payload.t_data.get("t_date") or payload.t_data.get(
        "date") or datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    t_method = payload.t_data.get(
        "t_method") or payload.t_data.get("method") or ""
    t_issuer = payload.t_data.get(
        "t_issuer") or payload.t_data.get("issuer") or ""
    t_bank = payload.t_data.get("t_bank") or payload.t_data.get("bank") or ""
    t_amount = payload.t_data.get("t_amount") or payload.t_data.get("amount")

    # mark as completed (use int flag) and save provider fields
    completed = 1
    completed_at = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    # Use database function to update payment
    updates = {
        "completed": completed,
        "t_date": t_date,
        "t_method": t_method,
        "t_issuer": t_issuer,
        "t_bank": t_bank,
        "t_amount": t_amount,
    }
    success = update_payment(con, transaction_id, updates)
    if not success:
        log_event(level="ERROR", event="payment_complete_failed",
                  username=user["username"], transaction_id=transaction_id, reason="db_error")
        raise HTTPException(500, detail="Failed to update payment")

    updated = con.execute(
        "SELECT * FROM payments WHERE transaction_id = ?", (transaction_id,)).fetchone()
    log_event(level="INFO", event="payment_complete_success",
              username=user["username"], transaction_id=transaction_id)
    return {"status": "Success", "payment_completed_at": completed_at, "payment": _row_to_dict(updated)}


@router.get("/payments")
def list_my_payments(user=Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    log_event(level="INFO", event="payment_list_own",
              username=user["username"])
    # Use database function to get user ID
    user_id = get_user_id_by_username(con, user.get("username"))
    if not user_id:
        return []
    # Use database function to get payments
    payments = get_payments_by_user_id(con, user_id)
    return payments


@router.get("/payments/billing")
def get_my_billing(user=Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    # Alias for /billing endpoint
    return my_billing(user, con)


@router.get("/payments/user/{user_name}")
def list_user_payments(user_name: str, admin=Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    log_event(level="INFO", event="payment_list_user",
              admin=admin["username"], target_user=user_name)
    # Use database function to get user ID
    user_id = get_user_id_by_username(con, user_name)
    if not user_id:
        return []
    # Use database function to get payments
    payments = get_payments_by_user_id(con, user_id)
    return payments


@router.get("/payments/{payment_id}")
def get_payment(payment_id: str, user=Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    """Get a single payment by ID"""
    log_event(level="INFO", event="payment_get_detail",
              username=user["username"], payment_id=payment_id)
    user_id = get_user_id_by_username(con, user.get("username"))
    if not user_id:
        log_event(level="ERROR", event="payment_get_failed",
                  username=user["username"], reason="user_not_found_in_db")
        raise HTTPException(404, detail="User not found")

    try:
        pid = int(payment_id)
    except ValueError:
        log_event(level="WARNING", event="payment_get_failed",
                  username=user["username"], payment_id=payment_id, reason="invalid_id_format")
        raise HTTPException(400, detail="Invalid payment ID")

    row = con.execute(
        "SELECT * FROM payments WHERE payment_id = ? AND user_id = ?",
        (pid, user_id)
    ).fetchone()

    if not row:
        raise HTTPException(404, detail="Payment not found")

    return _row_to_dict(row)


@router.get("/billing")
def my_billing(user=Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    log_event(level="INFO", event="billing_view_own",
              username=user["username"])
    # build billing view from DB sessions + parking_lots + payments
    # Use database function to get user ID
    user_id = get_user_id_by_username(con, user.get("username"))
    if not user_id:
        return []

    sessions = con.execute(
        "SELECT * FROM sessions WHERE user_id = ?", (user_id,)).fetchall()
    data = []
    for s in sessions:
        sdict = dict(s)
        sid = sdict.get("session_id")
        lot_id = sdict.get("parking_lot_id")
        vehicle_id = sdict.get("vehicle_id")

        # Get parking lot details
        lot = con.execute(
            "SELECT * FROM parking_lots WHERE id = ?", (lot_id,)).fetchone()
        lotd = dict(lot) if lot else {}
        parking = {
            "name": lotd.get("name"),
            "location": lotd.get("location"),
            "tariff": lotd.get("tariff"),
            "daytariff": lotd.get("daytariff"),
        }

        # Get vehicle/license plate
        licenseplate = ""
        if vehicle_id:
            vehicle = con.execute(
                "SELECT license_plate FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
            licenseplate = vehicle["license_plate"] if vehicle else ""

        session_obj = {
            "licenseplate": licenseplate,
            "started": sdict.get("started"),
            "stopped": sdict.get("stopped")
        }
        try:
            amount, hours, days = sc.calculate_price(
                parking, str(sid), session_obj)
        except Exception:
            amount, hours, days = 0, 0, 0
        paid_row = con.execute(
            "SELECT COALESCE(SUM(amount),0) as paid FROM payments WHERE session_id = ?", (sid,)).fetchone()
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
def user_billing(user_name: str, admin=Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    log_event(level="INFO", event="billing_view_user",
              admin=admin["username"], target_user=user_name)
    # Use database function to get user ID
    uid = get_user_id_by_username(con, user_name)
    if not uid:
        return []

    sessions = con.execute(
        "SELECT * FROM sessions WHERE user_id = ?", (uid,)).fetchall()
    data = []
    for s in sessions:
        sdict = dict(s)
        sid = sdict.get("session_id")
        lot_id = sdict.get("parking_lot_id")
        vehicle_id = sdict.get("vehicle_id")

        # Get parking lot details
        lot = con.execute(
            "SELECT * FROM parking_lots WHERE id = ?", (lot_id,)).fetchone()
        lotd = dict(lot) if lot else {}
        parking = {
            "name": lotd.get("name"),
            "location": lotd.get("location"),
            "tariff": lotd.get("tariff"),
            "daytariff": lotd.get("daytariff"),
        }

        # Get vehicle/license plate
        licenseplate = ""
        if vehicle_id:
            vehicle = con.execute(
                "SELECT license_plate FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
            licenseplate = vehicle["license_plate"] if vehicle else ""

        session_obj = {"licenseplate": licenseplate, "started": sdict.get(
            "started"), "stopped": sdict.get("stopped")}
        try:
            amount, hours, days = sc.calculate_price(
                parking, str(sid), session_obj)
        except Exception:
            amount, hours, days = 0, 0, 0
        paid_row = con.execute(
            "SELECT COALESCE(SUM(amount),0) as paid FROM payments WHERE session_id = ?", (sid,)).fetchone()
        paid = paid_row["paid"] if paid_row else 0
        data.append({
            "session": {"licenseplate": licenseplate, "started": session_obj["started"], "stopped": session_obj["stopped"], "hours": hours, "days": days},
            "parking": parking,
            "amount": amount,
            "payed": paid,
            "balance": amount - paid
        })
    return data
