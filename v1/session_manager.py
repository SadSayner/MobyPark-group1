from fastapi.params import Depends
from .Database.database_logic import get_connection, get_users_by_username

def add_session(token, user):
    with get_connection() as con:
        con.execute("INSERT INTO auth_sessions (token, user_id) VALUES (?, ?)", (token, user["id"]))
        con.commit()

def remove_session(token):
    with get_connection() as con:
        con.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
        con.commit()

def get_session(token):
    con = get_connection()
    try:
        cur = con.execute("SELECT token, user_id FROM auth_sessions WHERE token = ?", (token,))
        row = cur.fetchone()
        if row:
            user_id = row["user_id"]
            # Get full user data
            user_row = con.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if user_row:
                return {
                    "id": user_row["id"],
                    "username": user_row["username"],
                    "name": user_row["name"],
                    "role": user_row["role"]
                }
        return None
    finally:
        con.close()

    