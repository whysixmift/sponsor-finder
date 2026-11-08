from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func

from app.database.db import async_session_maker
from app.database.models import Sponsor, ProposalProfile

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")

@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    async with async_session_maker() as session:
        sponsors_count = (await session.execute(select(func.count(Sponsor.id)))).scalar_one()
        proposals_count = (await session.execute(select(func.count(ProposalProfile.id)))).scalar_one()

    return templates.TemplateResponse(request=request, name="landing.html", context={
        "sponsors_count": sponsors_count,
        "proposals_count": proposals_count
    })
