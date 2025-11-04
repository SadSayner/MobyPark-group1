
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
import hashlib, uuid

from dbm import sqlite3
from storage_utils import load_json, save_user_data
from session_manager import add_session, remove_session, get_session
from v1.server.deps import require_session
from v1.Database.database_logic import get_connection
from v1.server.validation.validation import is_valid_username, is_valid_password, is_valid_email, is_valid_phone, is_valid_role


router = APIRouter()

def hasher(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()

class RegisterIn(BaseModel):
    username: str
    password: str
    name: str
    role: Optional[str] = "USER"

class LoginIn(BaseModel):
    username: str
    password: str

def get_db():
    con = get_connection()
    try:
        yield con
    finally:
        try:
            con.close()
        except Exception:
            pass    

@router.post("/register")
def register(payload: RegisterIn, con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute("SELECT 1 FROM users WHERE username = ?", (payload.username,))
    if cur.fetchone():
        raise HTTPException(status_code=409, detail="Username already taken")
    con.execute(
        "INSERT INTO users (username, password, name, role) VALUES (?, ?, ?, ?)",
        (payload.username, hasher(payload.password), payload.name, (payload.role or "USER").upper()),
    )
    con.commit()
    return {"message": "User created"}

@router.post("/login")
def login(payload: LoginIn, con: sqlite3.Connection = Depends(get_db)):
    cur = con.execute(
        "SELECT username, name, role From users WHERE username = ? AND password = ?"
        , (payload.username, hasher(payload.password))
    )
    user = cur.fetchone()
    if user:
        session_token = str(uuid.uuid4())
        add_session(session_token, {"username": user[0], "name": user[1], "role": user[2]})
        return {"message": "Login successful", "session_token": session_token}
    raise HTTPException(status_code=401, detail="Invalid username or password")

@router.get("/profile")
def profile(user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)):
    """
    Return fresh profile data from the database (no password).
    Uses the session 'user' to identify which DB record to read.
    """
    cur = con.execute("SELECT username, name, role FROM users WHERE username = ?", (user["username"],))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return {"username": row[0], "name": row[1], "role": row[2]}

class UpdateProfileIn(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    
@router.put("/profile")
def update_profile(updates: UpdateProfileIn, user = Depends(require_session), con: sqlite3.Connection = Depends(get_db)): #Depends zorgt ervoor dat de require_session functie wordt aangeroepen voordat de variable 'user' kan worden gebruikt
    cur = con.execute("SELECT username, name, email, phone, role FROM users WHERE username = ?", (user["username"],))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    if updates.name is not None:
        cur.execute("UPDATE users SET name = ? WHERE username = ?", (updates.name, user["username"]))
    if updates.password:
        cur.execute("UPDATE users SET password = ? WHERE username = ?", (hasher(updates.password), user["username"]))
    if updates.role and user.get("role") == "ADMIN":
        cur.execute("UPDATE users SET role = ? WHERE username = ?", (updates.role, user["username"]))
    if updates.email is not None:
        cur.execute("UPDATE users SET email = ? WHERE username = ?", (updates.email, user["username"]))
    if updates.phone is not None:
        cur.execute("UPDATE users SET phone = ? WHERE username = ?", (updates.phone, user["username"]))
    con.commit()
    return {"message": "User updated successfully"}

@router.get("/logout")
def logout(authorization: Optional[str] = Header(default=None)): 
    if authorization and get_session(authorization):
        remove_session(authorization)
        return {"message": "User logged out"}
    raise HTTPException(400, detail="Invalid session token")
