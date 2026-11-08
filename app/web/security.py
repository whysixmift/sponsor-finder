from fastapi import Request, HTTPException, status
from app.config.settings import settings

def is_authenticated(request: Request) -> bool:
    session_val = request.session.get("admin_authenticated", False)
    return bool(session_val)

def require_admin(request: Request):
    if not is_authenticated(request):
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )
