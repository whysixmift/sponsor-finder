from typing import List, Optional, Tuple
from sqlalchemy import select, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Sponsor, AISponsorMatch, FavoriteSponsor, ProposalProfile
from app.utils.logger import logger

class SponsorService:
    async def get_all_sponsors(
        self,
        session: AsyncSession,
        category: Optional[str] = None,
        region: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Sponsor]:
        stmt = select(Sponsor)
        conditions = []

        if category and category.lower() != "all":
            conditions.append(Sponsor.category.ilike(f"%{category}%"))

        if region and region.lower() != "all":
            conditions.append(Sponsor.region.ilike(f"%{region}%"))

        if search_query:
            term = f"%{search_query.strip()}%"
            conditions.append(
                or_(
                    Sponsor.name.ilike(term),
                    Sponsor.description.ilike(term),
                    Sponsor.target_demographics.ilike(term),
                    Sponsor.typical_sponsorship.ilike(term)
                )
            )

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(Sponsor.id.desc()).offset(offset).limit(limit)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_sponsor_by_id(self, session: AsyncSession, sponsor_id: int) -> Optional[Sponsor]:
        stmt = select(Sponsor).where(Sponsor.id == sponsor_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_top_matches_for_user(
        self,
        session: AsyncSession,
        user_id: int,
        min_score: int = 70,
        limit: int = 20
    ) -> List[Tuple[AISponsorMatch, Sponsor]]:
        stmt = (
            select(AISponsorMatch, Sponsor)
            .join(Sponsor, AISponsorMatch.sponsor_id == Sponsor.id)
            .where(
                and_(
                    AISponsorMatch.user_id == user_id,
                    AISponsorMatch.score >= min_score
                )
            )
            .order_by(AISponsorMatch.score.desc())
            .limit(limit)
        )
        res = await session.execute(stmt)
        return list(res.all())

    async def toggle_favorite(self, session: AsyncSession, user_id: int, sponsor_id: int) -> bool:
        """Toggle favorite status. Returns True if now favorited, False if removed."""
        stmt = select(FavoriteSponsor).where(
            and_(FavoriteSponsor.user_id == user_id, FavoriteSponsor.sponsor_id == sponsor_id)
        )
        res = await session.execute(stmt)
        fav = res.scalar_one_or_none()

        if fav:
            await session.delete(fav)
            await session.commit()
            return False
        else:
            new_fav = FavoriteSponsor(user_id=user_id, sponsor_id=sponsor_id)
            session.add(new_fav)
            await session.commit()
            return True

    async def get_user_favorites(self, session: AsyncSession, user_id: int) -> List[Sponsor]:
        stmt = (
            select(Sponsor)
            .join(FavoriteSponsor, FavoriteSponsor.sponsor_id == Sponsor.id)
            .where(FavoriteSponsor.user_id == user_id)
            .order_by(FavoriteSponsor.created_at.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def add_or_update_sponsor(
        self,
        session: AsyncSession,
        name: str,
        website: Optional[str] = None,
        contact_email: Optional[str] = None,
        category: Optional[str] = None,
        region: str = "Indonesia",
        description: Optional[str] = None,
        typical_sponsorship: Optional[str] = None,
        target_demographics: Optional[str] = None,
        is_discovered: bool = True
    ) -> Sponsor:
        stmt = select(Sponsor).where(Sponsor.name.ilike(name.strip()))
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            if contact_email and not existing.contact_email:
                existing.contact_email = contact_email
            if website and not existing.website:
                existing.website = website
            if description and not existing.description:
                existing.description = description
            await session.commit()
            return existing

        sponsor = Sponsor(
            name=name.strip(),
            website=website,
            contact_email=contact_email,
            category=category,
            region=region,
            description=description,
            typical_sponsorship=typical_sponsorship,
            target_demographics=target_demographics,
            is_discovered=is_discovered,
            status="active"
        )
        session.add(sponsor)
        await session.commit()
        await session.refresh(sponsor)
        return sponsor

sponsor_service = SponsorService()
