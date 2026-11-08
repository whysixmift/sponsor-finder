from fastapi import APIRouter
from app.agents import ALL_AGENTS

router = APIRouter(prefix="/api")

@router.get("/status")
async def get_system_status():
    return {
        "status": "operational",
        "agents": [a.get_status() for a in ALL_AGENTS]
    }
