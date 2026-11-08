import os
import json
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config.settings import settings
from app.database.models import Base, Sponsor, UserWhitelist
from app.utils.logger import logger

def get_db_file_path() -> str:
    url = settings.DATABASE_URL
    if "sqlite" in url:
        return url.split("sqlite+aiosqlite:///")[-1].split("?")[0]
    return ""

# Engine setup
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"timeout": 30} if "sqlite" in settings.DATABASE_URL else {}
)

async_session_maker = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)

def refresh_engine() -> None:
    """Rebind engine dynamically if DATABASE_URL is updated."""
    global engine, async_session_maker
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        connect_args={"timeout": 30} if "sqlite" in settings.DATABASE_URL else {}
    )
    async_session_maker.configure(bind=engine)

async def seed_initial_sponsors(session: AsyncSession) -> None:
    """Populate default high-profile Indonesian and Global sponsors if table is empty."""
    count_stmt = select(func.count(Sponsor.id))
    res = await session.execute(count_stmt)
    count = res.scalar_one()

    if count == 0:
        seed_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "sponsors_seed.json")
        if os.path.exists(seed_path):
            try:
                with open(seed_path, "r", encoding="utf-8") as f:
                    seed_data = json.load(f)
                
                for item in seed_data:
                    sponsor = Sponsor(
                        name=item.get("name"),
                        website=item.get("website"),
                        partnership_url=item.get("partnership_url"),
                        contact_email=item.get("contact_email"),
                        category=item.get("category"),
                        region=item.get("region", "Indonesia"),
                        target_demographics=item.get("target_demographics"),
                        typical_sponsorship=item.get("typical_sponsorship"),
                        description=item.get("description"),
                        sponsorship_guidelines=item.get("sponsorship_guidelines"),
                        is_discovered=False,
                        status="active"
                    )
                    session.add(sponsor)
                
                await session.commit()
                logger.info(f"Successfully seeded {len(seed_data)} corporate sponsors into catalog.")
            except Exception as e:
                logger.error(f"Failed to seed sponsors: {e}")
                await session.rollback()

async def ensure_admin_whitelisted(session: AsyncSession) -> None:
    """Ensure the configured TELEGRAM_ADMIN_ID is whitelisted."""
    admin_id = settings.TELEGRAM_ADMIN_ID
    if not admin_id:
        return
    
    stmt = select(UserWhitelist).where(UserWhitelist.telegram_id == admin_id)
    res = await session.execute(stmt)
    admin = res.scalar_one_or_none()
    if not admin:
        admin_entry = UserWhitelist(
            telegram_id=admin_id,
            notes="Default Superadmin",
            status="approved",
            is_active=True
        )
        session.add(admin_entry)
        await session.commit()
        logger.info(f"Superadmin Telegram ID {admin_id} whitelisted successfully.")

async def init_db() -> None:
    """Initialize DB tables, run schema setup, and seed initial records."""
    db_file = get_db_file_path()
    if db_file:
        os.makedirs(os.path.dirname(db_file) or ".", exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as session:
        await seed_initial_sponsors(session)
        await ensure_admin_whitelisted(session)

    logger.info("Database initialized successfully.")
