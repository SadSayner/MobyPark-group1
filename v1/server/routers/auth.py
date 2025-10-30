
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
import hashlib, uuid

from dbm import sqlite3
from storage_utils import load_json, save_user_data
from session_manager import add_session, remove_session, get_session
from v1.server.deps import require_session
from v1.Database.database_logic import get_connection


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
    # check existing user
    cur = con.execute("SELECT 1 FROM users WHERE username = ?", (payload.username,))
    if cur.fetchone():
        raise HTTPException(status_code=409, detail="Username already taken")
    # insert user
    con.execute(
        "INSERT INTO users (username, password, name, role) VALUES (?, ?, ?, ?)",
        (payload.username, hasher(payload.password), payload.name, (payload.role or "USER").upper()),
    )
    con.commit()
    return {"message": "User created"}

@router.post("/login")
def login(payload: LoginIn):
    users = load_json("data/users.json") or [] #replace with database
    hashed_pw = hasher(payload.password)
    matched_user = None
    for u in users:
        if u.get("username") == payload.username and u.get("password") == hashed_pw:
            matched_user = u
            break
    if not matched_user:
        raise HTTPException(401, detail="Invalid credentials")
    token = str(uuid.uuid4())
    add_session(token, matched_user)
    return {"message": "User logged in", "session_token": token}

@router.get("/profile") #laat alles in zn profiel zien behalve wachtwoord
def profile(user = Depends(require_session)): #Depends zorgt ervoor dat de require_session functie wordt aangeroepen voordat de variable 'user' kan worden gebruikt
    return {
        "username": user.get("username"),
        "name": user.get("name"),
        "role": user.get("role")
    }

class UpdateProfileIn(BaseModel): #basemodel is van pydantic, het defined de structuur van de data die we verwachten
    name: Optional[str] = None #optioneel veld, kan leeg gelaten worden
    password: Optional[str] = None #optioneel veld, kan leeg gelaten worden
    role: Optional[str] = None #optioneel veld, kan leeg gelaten worden

@router.put("/profile")
def update_profile(payload: UpdateProfileIn, user = Depends(require_session)): #Depends zorgt ervoor dat de require_session functie wordt aangeroepen voordat de variable 'user' kan worden gebruikt
    users = load_json("data/users.json") or []
    for u in users:
        if u.get("username") == user["username"]:
            if payload.name is not None:
                u["name"] = payload.name
            if payload.password:
                u["password"] = hasher(payload.password)
            if payload.role and user.get("role") == "ADMIN":
                u["role"] = payload.role
            save_user_data(users)
            return {"message": "User updated successfully"}
    raise HTTPException(404, detail="User not found")

@router.get("/logout")
def logout(authorization: Optional[str] = Header(default=None)): 
    if authorization and get_session(authorization):
        remove_session(authorization)
        return {"message": "User logged out"}
    raise HTTPException(400, detail="Invalid session token")
