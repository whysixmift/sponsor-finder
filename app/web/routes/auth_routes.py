from typing import Optional
from fastapi import APIRouter, Request, Form, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.config.settings import settings
from app.database.db import async_session_maker
from app.services.google_auth_service import google_auth_service
from app.utils.logger import logger

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("admin_authenticated"):
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})

@router.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request, password: str = Form(...)):
    if password == settings.ADMIN_PASSWORD:
        request.session["admin_authenticated"] = True
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={"error": "Password salah, silakan coba lagi."})

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@router.get("/auth/google/callback")
async def google_oauth_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None):
    if not code:
        return HTMLResponse("<h3>Gagal: Kode otorisasi tidak ditemukan.</h3>", status_code=400)
    
    try:
        user_id = int(state) if state else settings.TELEGRAM_ADMIN_ID
    except Exception:
        user_id = settings.TELEGRAM_ADMIN_ID

    async with async_session_maker() as session:
        success, res_msg = await google_auth_service.handle_oauth_callback(session, code, user_id)

    if success:
        return templates.TemplateResponse(request=request, name="google_success.html", context={
            "email": res_msg,
            "user_id": user_id
        })
    else:
        return HTMLResponse(f"<h3>Otorisasi Gagal:</h3><p>{res_msg}</p>", status_code=500)
