import json
from typing import List, Tuple, Dict, Any, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base_agent import BaseAgent
from app.config.settings import settings
from app.database.db import async_session_maker
from app.database.models import Sponsor, AISponsorMatch, ProposalProfile
from app.ai.evaluator import evaluator
from app.utils.logger import logger

class MatchingAgent(BaseAgent):
    """Autonomous agent for semantic matching and scoring of sponsors against event proposals."""

    def __init__(self) -> None:
        super().__init__(
            agent_name="MatchingAgent",
            feature_description="Semantic AI Sponsor Matcher & ROI Scoring Engine"
        )

    async def match_sponsors_for_user(
        self,
        user_id: int,
        sponsors: Optional[List[Sponsor]] = None,
        force_reevaluate: bool = False
    ) -> List[Tuple[AISponsorMatch, Sponsor]]:
        """Evaluate catalog sponsors against the user's submitted proposal."""
        start = self.mark_start()
        matches: List[Tuple[AISponsorMatch, Sponsor]] = []

        try:
            async with async_session_maker() as session:
                # 1. Fetch user's proposal
                prop_stmt = select(ProposalProfile).where(ProposalProfile.user_id == user_id)
                res_prop = await session.execute(prop_stmt)
                proposal = res_prop.scalar_one_or_none()

                if not proposal:
                    logger.warning(f"No proposal uploaded for user {user_id}. Using default generic event context.")
                    proposal_text = "National Student Technology and Innovation Summit. Audience: 500+ university and vocational students, developers, creators. Seeking cash sponsorship, tech tools, product in-kind, and keynote speakers."
                    proposal_id = None
                else:
                    proposal_text = proposal.full_text
                    proposal_id = proposal.id

                # 2. Fetch sponsors if not provided
                if not sponsors:
                    s_stmt = select(Sponsor).where(Sponsor.status == "active").limit(settings.MAX_SPONSORS_PER_RUN)
                    s_res = await session.execute(s_stmt)
                    sponsors = list(s_res.scalars().all())

                for sponsor in sponsors:
                    try:
                        # Check existing match cache
                        cache_stmt = select(AISponsorMatch).where(
                            and_(AISponsorMatch.user_id == user_id, AISponsorMatch.sponsor_id == sponsor.id)
                        )
                        cache_res = await session.execute(cache_stmt)
                        existing_match = cache_res.scalar_one_or_none()

                        if existing_match and not force_reevaluate:
                            if existing_match.recommended and existing_match.score >= settings.SCORE_THRESHOLD:
                                matches.append((existing_match, sponsor))
                            continue

                        # Evaluate fit with AI
                        eval_result = await evaluator.evaluate_sponsor_fit(
                            sponsor_name=sponsor.name,
                            category=sponsor.category or "General",
                            description=sponsor.description or "",
                            target_demographics=sponsor.target_demographics or "",
                            proposal_text=proposal_text
                        )

                        if existing_match:
                            existing_match.score = eval_result.score
                            existing_match.recommended = eval_result.recommended
                            existing_match.reason = "\n".join(eval_result.reason) if isinstance(eval_result.reason, list) else str(eval_result.reason)
                            existing_match.value_proposition_angle = eval_result.value_proposition_angle
                            existing_match.suggested_tier = eval_result.suggested_tier
                            existing_match.matched_demographics = json.dumps(eval_result.matched_demographics, ensure_ascii=False)
                            existing_match.summary = eval_result.summary
                            existing_match.priority = eval_result.priority
                            match_rec = existing_match
                        else:
                            match_rec = AISponsorMatch(
                                user_id=user_id,
                                proposal_id=proposal_id,
                                sponsor_id=sponsor.id,
                                score=eval_result.score,
                                recommended=eval_result.recommended,
                                reason="\n".join(eval_result.reason) if isinstance(eval_result.reason, list) else str(eval_result.reason),
                                value_proposition_angle=eval_result.value_proposition_angle,
                                suggested_tier=eval_result.suggested_tier,
                                matched_demographics=json.dumps(eval_result.matched_demographics, ensure_ascii=False),
                                summary=eval_result.summary,
                                priority=eval_result.priority
                            )
                            session.add(match_rec)

                        await session.commit()
                        if match_rec.recommended and match_rec.score >= settings.SCORE_THRESHOLD:
                            matches.append((match_rec, sponsor))

                    except Exception as err:
                        logger.error(f"Error evaluating sponsor #{sponsor.id} ({sponsor.name}): {err}")
                        continue

            matches.sort(key=lambda m: m[0].score, reverse=True)
            self.mark_success(start)
            return matches

        except Exception as e:
            self.mark_failure(start, e)
            return []

matching_agent = MatchingAgent()
