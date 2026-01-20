
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
import bcrypt, uuid, hashlib

import sqlite3
from ...storage_utils import load_json, save_user_data
from ...session_manager import add_session, remove_session, get_session
from ..deps import require_session
from ...Database.database_logic import get_db, get_users_by_username, get_user_by_email, update_user
from ..validation.validation import (
    is_valid_username,
    is_valid_password,
    is_valid_email,
    is_valid_phone,
    is_valid_role,
    is_valid_license_plate
)


router = APIRouter()

def hash_password(password: str) -> str:
    """Hash a password using bcrypt with automatic salt generation"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed: str) -> tuple[bool, bool]:
    """
    Verify a password against a hash.
    Supports both bcrypt (new) and MD5 (legacy) for backwards compatibility.

    Returns:
        tuple[bool, bool]: (is_valid, needs_upgrade)
            - is_valid: True if password matches the hash
            - needs_upgrade: True if hash is MD5 and should be upgraded to bcrypt
    """
    #Check if it's an MD5 hash (32 hex characters)
    if len(hashed) == 32 and all(c in '0123456789abcdef' for c in hashed.lower()):
        # Legacy MD5 hash - for backwards compatibility
        md5_hash = hashlib.md5(password.encode()).hexdigest()
        is_valid = md5_hash == hashed
        return (is_valid, is_valid)  # If valid, needs upgrade from MD5 to bcrypt

    #Modern bcrypt hash
    try:
        is_valid = bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        return (is_valid, False)  # bcrypt hash doesn't need upgrade
    except ValueError:
        # Invalid hash format
        return (False, False)

class RegisterBody(BaseModel):
    username: str
    password: str
    name: str
    email: str
    phone: str
    role: Optional[str] = "USER"

class LoginBody(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    password: str

class UpdateProfileIn(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

@router.post("/register")
def register(payload: RegisterBody, con: sqlite3.Connection = Depends(get_db)):
    if not is_valid_username(payload.username):
        raise HTTPException(
            status_code=400,
            detail="Invalid username. Must be 8-10 characters, start with a letter or underscore, and contain only letters, numbers, underscores, apostrophes, or periods."
        )

    if not is_valid_password(payload.password):
        raise HTTPException(
            status_code=400,
            detail="Invalid password. Must be 12-30 characters and contain at least one lowercase letter, one uppercase letter, one digit, and one special character."
        )

    if not is_valid_email(payload.email):
        raise HTTPException(status_code=400, detail="Invalid email format.")

    if not is_valid_phone(payload.phone):
        raise HTTPException(
            status_code=400,
            detail="Invalid phone number. Must be 7-15 digits with optional separators (+, -, spaces, parentheses)."
        )

    if payload.role and not is_valid_role(payload.role):
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'USER' or 'ADMIN'.")

    existing_user = get_users_by_username(con, payload.username)
    if existing_user:
        raise HTTPException(status_code=409, detail="Username already taken")

    con.execute(
        "INSERT INTO users (username, password, name, email, phone, role, created_at, birth_year, active) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1990, 1)",
        (payload.username, hash_password(payload.password), payload.name, payload.email, payload.phone, (payload.role or "USER").upper()),
    )
    con.commit()
    return {"message": "User created"}

@router.post("/login")
def login(payload: LoginBody, con: sqlite3.Connection = Depends(get_db)):
    if not payload.password:
        raise HTTPException(status_code=400, detail="Password is required")

    if not payload.email and not payload.username:
        raise HTTPException(status_code=400, detail="Email or username is required")

    # Try to find user by email first, then by username
    user = None
    if payload.email:
        user = get_user_by_email(con, payload.email)
    elif payload.username:
        # If username looks like an email, try email lookup first
        if '@' in payload.username:
            user = get_user_by_email(con, payload.username)
        # If not found, try username lookup
        if not user:
            user = get_users_by_username(con, payload.username)

    if user:
        is_valid, needs_upgrade = verify_password(payload.password, user.password)
        if is_valid:
            # Automatically upgrade MD5 password to bcrypt
            if needs_upgrade:
                new_hash = hash_password(payload.password)
                update_user(con, user.username, {"password": new_hash})

            session_token = str(uuid.uuid4())
            add_session(session_token, {"id": user.id, "username": user.username, "name": user.name, "role": user.role})
            return {"message": "Login successful", "session_token": session_token}

    raise HTTPException(status_code=401, detail="Invalid credentials")

@router.get("/profile")
def profile(user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    db_user = get_users_by_username(con, user["username"])
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"username": db_user.username, "name": db_user.name, "role": db_user.role}
    
@router.put("/profile")
def update_profile(updates: UpdateProfileIn, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    db_user = get_users_by_username(con, user["username"])
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if updates.password is not None:
        if not is_valid_password(updates.password):
            raise HTTPException(
                status_code=400,
                detail="Invalid password. Must be 12-30 characters and contain at least one lowercase letter, one uppercase letter, one digit, and one special character."
            )

    if updates.email is not None:
        if not is_valid_email(updates.email):
            raise HTTPException(status_code=400, detail="Invalid email format.")

    if updates.phone is not None:
        if not is_valid_phone(updates.phone):
            raise HTTPException(
                status_code=400,
                detail="Invalid phone number. Must be 7-15 digits with optional separators (+, -, spaces, parentheses)."
            )

    if updates.role is not None:
        if not is_valid_role(updates.role):
            raise HTTPException(status_code=400, detail="Invalid role. Must be 'USER' or 'ADMIN'.")

    update_dict = {}
    if updates.name is not None:
        update_dict["name"] = updates.name
    if updates.password:
        update_dict["password"] = hash_password(updates.password)
    if updates.role and user.get("role") == "ADMIN":
        update_dict["role"] = updates.role
    if updates.email is not None:
        update_dict["email"] = updates.email
    if updates.phone is not None:
        update_dict["phone"] = updates.phone

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
