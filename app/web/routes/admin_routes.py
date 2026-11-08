import os
from typing import Optional
from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, desc

from app.config.settings import settings
from app.database.db import async_session_maker
from app.database.models import Sponsor, ProposalProfile, EmailQueue, UserWhitelist, AISponsorMatch
from app.agents import ALL_AGENTS
from app.agents.sponsor_discovery_agent import sponsor_discovery_agent
from app.web.security import is_authenticated
from app.utils.logger import logger

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/web/templates")

def check_admin(request: Request):
    if not is_authenticated(request):
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )

@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request, _ = Depends(check_admin)):
    async with async_session_maker() as session:
        # Overview stats
        sponsors_count = (await session.execute(select(func.count(Sponsor.id)))).scalar_one()
        proposals_count = (await session.execute(select(func.count(ProposalProfile.id)))).scalar_one()
        emails_count = (await session.execute(select(func.count(EmailQueue.id)))).scalar_one()
        users_count = (await session.execute(select(func.count(UserWhitelist.id)))).scalar_one()

        # Recent sponsors
        recent_sponsors_res = await session.execute(select(Sponsor).order_by(desc(Sponsor.id)).limit(5))
        recent_sponsors = list(recent_sponsors_res.scalars().all())

    agents_telemetry = [agent.get_status() for agent in ALL_AGENTS]

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "sponsors_count": sponsors_count,
        "proposals_count": proposals_count,
        "emails_count": emails_count,
        "users_count": users_count,
        "recent_sponsors": recent_sponsors,
        "agents": agents_telemetry
    })

@router.get("/sponsors", response_class=HTMLResponse)
async def list_sponsors(
    request: Request,
    q: Optional[str] = None,
    cat: Optional[str] = None,
    region: Optional[str] = None,
    _ = Depends(check_admin)
):
    async with async_session_maker() as session:
        stmt = select(Sponsor)
        conditions = []
        if q:
            term = f"%{q.strip()}%"
            conditions.append(Sponsor.name.ilike(term))
        if cat and cat != "all":
            conditions.append(Sponsor.category.ilike(f"%{cat}%"))
        if region and region != "all":
            conditions.append(Sponsor.region == region)
        
        if conditions:
            from sqlalchemy import and_
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(desc(Sponsor.id)).limit(100)
        res = await session.execute(stmt)
        sponsors = list(res.scalars().all())

    return templates.TemplateResponse(request=request, name="sponsors.html", context={
        "sponsors": sponsors,
        "q": q or "",
        "cat": cat or "all",
        "region": region or "all"
    })

@router.post("/sponsors/add")
async def add_sponsor_manual(
    request: Request,
    name: str = Form(...),
    website: Optional[str] = Form(None),
    contact_email: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    region: str = Form("Indonesia"),
    typical_sponsorship: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    _ = Depends(check_admin)
):
    async with async_session_maker() as session:
        sponsor = Sponsor(
            name=name.strip(),
            website=website,
            contact_email=contact_email,
            category=category,
            region=region,
            typical_sponsorship=typical_sponsorship,
            description=description,
            is_discovered=False,
            status="active"
        )
        session.add(sponsor)
        await session.commit()
    return RedirectResponse(url="/admin/sponsors", status_code=303)

@router.get("/emails", response_class=HTMLResponse)
async def list_emails(request: Request, _ = Depends(check_admin)):
    async with async_session_maker() as session:
        stmt = select(EmailQueue, Sponsor).join(Sponsor, EmailQueue.sponsor_id == Sponsor.id).order_by(desc(EmailQueue.id)).limit(50)
        res = await session.execute(stmt)
        items = list(res.all())

    return templates.TemplateResponse(request=request, name="emails.html", context={
        "items": items
    })

@router.get("/users", response_class=HTMLResponse)
async def list_users(request: Request, _ = Depends(check_admin)):
    async with async_session_maker() as session:
        stmt = select(UserWhitelist).order_by(desc(UserWhitelist.id))
        res = await session.execute(stmt)
        users = list(res.scalars().all())

    return templates.TemplateResponse(request=request, name="users.html", context={
        "users": users
    })

@router.post("/users/add")
async def add_whitelist_user(
    request: Request,
    identifier: str = Form(...),
    notes: Optional[str] = Form(None),
    _ = Depends(check_admin)
):
    identifier = identifier.strip()
    tg_id = None
    username = None

    if identifier.isdigit():
        tg_id = int(identifier)
    else:
        username = identifier.lstrip("@")

    async with async_session_maker() as session:
        entry = UserWhitelist(
            telegram_id=tg_id,
            username=username,
            notes=notes,
            status="approved",
            is_active=True
        )
        session.add(entry)
        await session.commit()

    return RedirectResponse(url="/admin/users", status_code=303)

@router.post("/users/toggle/{user_id}")
async def toggle_whitelist_user(user_id: int, _ = Depends(check_admin)):
    async with async_session_maker() as session:
        stmt = select(UserWhitelist).where(UserWhitelist.id == user_id)
        res = await session.execute(stmt)
        entry = res.scalar_one_or_none()
        if entry:
            entry.is_active = not entry.is_active
            await session.commit()
    return RedirectResponse(url="/admin/users", status_code=303)

@router.post("/users/delete/{user_id}")
async def delete_whitelist_user(user_id: int, _ = Depends(check_admin)):
    async with async_session_maker() as session:
        stmt = select(UserWhitelist).where(UserWhitelist.id == user_id)
        res = await session.execute(stmt)
        entry = res.scalar_one_or_none()
        if entry:
            await session.delete(entry)
            await session.commit()
    return RedirectResponse(url="/admin/users", status_code=303)

@router.get("/settings", response_class=HTMLResponse)
async def view_settings(request: Request, _ = Depends(check_admin)):
    env_path = ".env"
    raw_env = ""
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            raw_env = f.read()

    return templates.TemplateResponse(request=request, name="settings.html", context={
        "settings": settings,
        "raw_env": raw_env
    })

@router.post("/settings/save")
async def save_settings(request: Request, raw_env: str = Form(...), _ = Depends(check_admin)):
    env_path = ".env"
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(raw_env)
    return RedirectResponse(url="/admin/settings", status_code=303)

@router.post("/trigger/discovery")
async def trigger_discovery(_ = Depends(check_admin)):
    await sponsor_discovery_agent.run_discovery(limit=5)
    return RedirectResponse(url="/admin/sponsors", status_code=303)
