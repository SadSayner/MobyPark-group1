
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
import hashlib, uuid

import sqlite3
from ...storage_utils import load_json, save_user_data
from ...session_manager import add_session, remove_session, get_session
from ..deps import require_session
from ...Database.database_logic import get_db, get_users_by_username, update_user
from ..validation.validation import is_valid_username, is_valid_password, is_valid_email, is_valid_phone, is_valid_role


router = APIRouter()

def hasher(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()

class RegisterIn(BaseModel):
    username: str
    password: str
    name: str
    email: str
    phone: str
    role: Optional[str] = "USER"

class LoginIn(BaseModel):
    username: str
    password: str

@router.post("/register")
def register(payload: RegisterIn, con: sqlite3.Connection = Depends(get_db)):
    # Check if username already exists
    existing_user = get_users_by_username(con, payload.username)
    if existing_user:
        raise HTTPException(status_code=409, detail="Username already taken")

    # Direct insert with all required fields
    con.execute(
        "INSERT INTO users (username, password, name, email, phone, role, created_at, birth_year, active) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1990, 1)",
        (payload.username, hasher(payload.password), payload.name, payload.email, payload.phone, (payload.role or "USER").upper()),
    )
    con.commit()
    return {"message": "User created"}

@router.post("/login")
def login(payload: LoginIn, con: sqlite3.Connection = Depends(get_db)):
    # Get user by username
    user = get_users_by_username(con, payload.username)

    if user and user.password == hasher(payload.password):
        session_token = str(uuid.uuid4())
        add_session(session_token, {"id": user.id, "username": user.username, "name": user.name, "role": user.role})
        return {"message": "Login successful", "session_token": session_token}
    raise HTTPException(status_code=401, detail="Invalid username or password")

@router.get("/profile")
def profile(user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    """
    Return fresh profile data from the database (no password).
    Uses the session 'user' to identify which DB record to read.
    """
    db_user = get_users_by_username(con, user["username"])
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"username": db_user.username, "name": db_user.name, "role": db_user.role}

class UpdateProfileIn(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    
@router.put("/profile")
def update_profile(updates: UpdateProfileIn, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    """
    Update user profile using database function.
    """
    # Check if user exists
    db_user = get_users_by_username(con, user["username"])
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Build updates dictionary
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

    # Use database function to update
    success = update_user(con, user["username"], update_dict)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update user")

    return {"message": "User updated successfully"}

@router.get("/logout")
def logout(authorization: Optional[str] = Header(default=None)): 
    if authorization and get_session(authorization):
        remove_session(authorization)
        return {"message": "User logged out"}
    raise HTTPException(400, detail="Invalid session token")
