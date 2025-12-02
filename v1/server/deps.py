
from fastapi import Header, HTTPException, Depends
from typing import Optional, Dict, Any
from ..session_manager import get_session

#de dependencies die we gebruiken in de routers
#de session token is de header
#je kan alleen require session method gecalled krijgen als je bent ingelogd, de session token is altijd meegegeven
def require_session(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if not authorization:
        raise HTTPException(401, detail="Missing Authorization header")
    user = get_session(authorization)
    if not user:
        raise HTTPException(401, detail="Invalid or expired session token")
    return user

def require_admin(user = Depends(require_session)):
    if user.get("role") != "ADMIN":
        raise HTTPException(403, detail="Access denied")
    return user
