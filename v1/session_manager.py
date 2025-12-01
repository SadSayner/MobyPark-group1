from fastapi.params import Depends
from Database.database_logic import get_connection

def add_session(token, user):
    with get_connection() as con:
        con.execute("INSERT INTO auth_sessions (token, user_id) VALUES (?, ?)", (token, user["id"]))
        con.commit()

def remove_session(token):
    with get_connection() as con:
        con.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
        con.commit()

def get_session(token, con=Depends(get_connection)):
    with con:
        cur = con.execute("SELECT token, user_id FROM auth_sessions WHERE token = ?", (token,))
        return cur.fetchone()
    return None

    