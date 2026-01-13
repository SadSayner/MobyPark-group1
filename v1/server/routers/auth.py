
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
import hashlib
import uuid


import sqlite3
from v1.server.logging_config import log_event
from ...storage_utils import load_json, save_user_data
from ...session_manager import add_session, remove_session, get_session
from ..deps import require_session
from ...Database.database_logic import get_db, get_users_by_username, update_user
from ..validation.validation import (
    is_valid_username,
    is_valid_password,
    is_valid_email,
    is_valid_phone,
    is_valid_role,
    is_valid_license_plate
)


router = APIRouter()


def hasher(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


class RegisterBody(BaseModel):
    username: str
    password: str
    name: str
    email: str
    phone: str
    role: Optional[str] = "USER"


class LoginBody(BaseModel):
    username: str
    password: str


class UpdateProfileIn(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


@router.post("/register")
def register(payload: RegisterBody, con: sqlite3.Connection = Depends(get_db)):
    log_event("INFO", event="register_attempt", username=payload.username)

    if not is_valid_username(payload.username):
        log_event("WARNING", event="register_failed",
                  username=payload.username, reason="invalid_username")
        raise HTTPException(
            status_code=400,
            detail="Invalid username. Must be 8-10 characters, start with a letter or underscore, and contain only letters, numbers, underscores, apostrophes, or periods."
        )

    if not is_valid_password(payload.password):
        log_event("WARNING", event="register_failed",
                  username=payload.username, reason="invalid_password")
        raise HTTPException(
            status_code=400,
            detail="Invalid password. Must be 12-30 characters and contain at least one lowercase letter, one uppercase letter, one digit, and one special character."
        )

    if not is_valid_email(payload.email):
        log_event("WARNING", event="register_failed",
                  username=payload.username, reason="invalid_email")
        raise HTTPException(status_code=400, detail="Invalid email format.")

    if not is_valid_phone(payload.phone):
        log_event("WARNING", event="register_failed",
                  username=payload.username, reason="invalid_phone")
        raise HTTPException(
            status_code=400,
            detail="Invalid phone number. Must be 7-15 digits with optional separators (+, -, spaces, parentheses)."
        )

    if payload.role and not is_valid_role(payload.role):
        log_event("WARNING", event="register_failed",
                  username=payload.username, reason="invalid_role")
        raise HTTPException(
            status_code=400, detail="Invalid role. Must be 'USER' or 'ADMIN'.")

    existing_user = get_users_by_username(con, payload.username)
    if existing_user:
        log_event("WARNING", event="register_failed",
                  username=payload.username, reason="username_taken")
        raise HTTPException(status_code=409, detail="Username already taken")

    con.execute(
        "INSERT INTO users (username, password, name, email, phone, role, created_at, birth_year, active) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1990, 1)",
        (payload.username, hasher(payload.password), payload.name,
         payload.email, payload.phone, (payload.role or "USER").upper()),
    )
    con.commit()

    log_event(
        "INFO",
        event="register_success",
        username=payload.username,
        role=(payload.role or "USER").upper()
    )

    return {"message": "User created"}


@router.post("/login")
def login(payload: LoginBody, con: sqlite3.Connection = Depends(get_db)):
    log_event("INFO", event="login_attempt", username=payload.username)
    if not payload.username or not payload.password:
        raise HTTPException(
            status_code=400, detail="Username and password are required")

    user = get_users_by_username(con, payload.username)

    if user and user.password == hasher(payload.password):
        session_token = str(uuid.uuid4())
        add_session(session_token, {
                    "id": user.id, "username": user.username, "name": user.name, "role": user.role})
        log_event("INFO", event="login_success",
                  username=user.username, role=user.role)
        return {"message": "Login successful", "session_token": session_token}
    log_event("WARNING", event="login_failed",
              username=payload.username, reason="invalid_credentials")
    raise HTTPException(status_code=401, detail="Invalid username or password")


@router.get("/profile")
def profile(user=Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    log_event("INFO", event="profile_view", username=user["username"])
    db_user = get_users_by_username(con, user["username"])
    if not db_user:
        log_event("ERROR", event="profile_view_failed",
                  username=user["username"], reason="not_found")
        raise HTTPException(status_code=404, detail="User not found")
    return {"username": db_user.username, "name": db_user.name, "role": db_user.role}


@router.put("/profile")
def update_profile(updates: UpdateProfileIn, user=Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    db_user = get_users_by_username(con, user["username"])

    fields_updated = list(updates.model_dump(exclude_none=True).keys())

    log_event(
        level="INFO",
        event="profile_update_attempt",
        username=user["username"],
        fields=fields_updated
    )

    if not db_user:
        log_event(level="ERROR", event="profile_update_failed",
                  username=user["username"], reason="not_found")
        raise HTTPException(status_code=404, detail="User not found")

    if updates.password is not None:
        if not is_valid_password(updates.password):
            log_event(level="WARNING", event="profile_update_failed",
                      username=user["username"], reason="invalid_password")
            raise HTTPException(
                status_code=400,
                detail="Invalid password. Must be 12-30 characters and contain at least one lowercase letter, one uppercase letter, one digit, and one special character."
            )

    if updates.email is not None:
        if not is_valid_email(updates.email):
            log_event(level="ERROR", event="profile_update_failed",
                      username=user["username"], reason="invalid_email")
            raise HTTPException(
                status_code=400, detail="Invalid email format.")

    if updates.phone is not None:
        if not is_valid_phone(updates.phone):
            log_event(level="ERROR", event="profile_update_failed",
                      username=user["username"], reason="invalid_phone")
            raise HTTPException(
                status_code=400,
                detail="Invalid phone number. Must be 7-15 digits with optional separators (+, -, spaces, parentheses)."
            )

    if updates.role is not None:
        if not is_valid_role(updates.role):
            raise HTTPException(
                status_code=400, detail="Invalid role. Must be 'USER' or 'ADMIN'.")

    update_dict = {}
    if updates.name is not None:
        update_dict["name"] = updates.name
    if updates.password:
        update_dict["password"] = hasher(updates.password)
    if updates.role and user.get("role") == "ADMIN":
        update_dict["role"] = updates.role
    if updates.email is not None:
        update_dict["email"] = updates.email
    if updates.phone is not None:
        update_dict["phone"] = updates.phone

    success = update_user(con, user["username"], update_dict)
    if not success:
        log_event(level="ERROR", event="profile_update_failed",
                  username=user["username"], reason="db_error")
        raise HTTPException(status_code=500, detail="Failed to update user")

    return {"message": "User updated successfully"}


@router.get("/logout")
def logout(authorization: Optional[str] = Header(default=None)):
    if authorization and get_session(authorization):
        user = get_session(authorization)

        if user:
            log_event(level="INFO", event="logout",
                      username=user.get("username"))

        remove_session(authorization)
        return {"message": "User logged out"}

    log_event(level="WARNING", event="logout_failed", reason="invalid_session")
    raise HTTPException(400, detail="Invalid session token")
