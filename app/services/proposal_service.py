import os
import io
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import pypdf
import docx

from app.database.models import ProposalProfile
from app.ai.evaluator import evaluator
from app.utils.logger import logger

class ProposalService:
    def __init__(self, upload_dir: str = "data/proposals") -> None:
        self.upload_dir = upload_dir
        os.makedirs(self.upload_dir, exist_ok=True)

    def extract_text_from_bytes(self, filename: str, file_bytes: bytes) -> str:
        """Extract plain text from PDF, DOCX, or text files."""
        ext = filename.lower().split(".")[-1]
        text = ""

        if ext == "pdf":
            try:
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                pages_text = [page.extract_text() or "" for page in reader.pages]
                text = "\n".join(pages_text).strip()
            except Exception as e:
                logger.error(f"Error parsing PDF proposal: {e}")
                raise ValueError(f"Could not read PDF proposal: {e}")
        elif ext in ["docx", "doc"]:
            try:
                doc = docx.Document(io.BytesIO(file_bytes))
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                text = "\n".join(paragraphs).strip()
            except Exception as e:
                logger.error(f"Error parsing DOCX proposal: {e}")
                raise ValueError(f"Could not read Word document: {e}")
        elif ext in ["txt", "md"]:
            try:
                text = file_bytes.decode("utf-8", errors="ignore").strip()
            except Exception as e:
                raise ValueError(f"Could not decode text file: {e}")
        else:
            raise ValueError(f"Unsupported format .{ext}. Please upload a PDF (.pdf) or Word document (.docx).")

        if not text or len(text.strip()) < 50:
            raise ValueError("The uploaded proposal contains insufficient text or could not be parsed.")

        return text

    async def save_proposal(
        self,
        session: AsyncSession,
        user_id: int,
        filename: str,
        file_bytes: bytes
    ) -> ProposalProfile:
        """Extract text, persist physical file to data/proposals, analyze with AI, and save profile."""
        text = self.extract_text_from_bytes(filename, file_bytes)

        # Persist physical file
        safe_name = f"{user_id}_{int(datetime.now().timestamp())}_{filename.replace(' ', '_')}"
        file_path = os.path.join(self.upload_dir, safe_name)
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        # AI Document analysis
        ai_meta = await evaluator.analyze_proposal_document(text)

        stmt = select(ProposalProfile).where(ProposalProfile.user_id == user_id)
        res = await session.execute(stmt)
        profile = res.scalar_one_or_none()

        title = ai_meta.get("title") or filename.rsplit(".", 1)[0]
        event_type = ai_meta.get("event_type", "General Event")
        target_audience = ai_meta.get("target_audience", "")
        expected_attendees = ai_meta.get("expected_attendees", "")
        location = ai_meta.get("location", "")
        event_date = ai_meta.get("event_date", "")
        requested_budget = ai_meta.get("requested_budget", "")
        tiers_json = json.dumps(ai_meta.get("sponsorship_tiers", {}), ensure_ascii=False)
        topics_json = json.dumps(ai_meta.get("detected_topics", []), ensure_ascii=False)
        summary = ai_meta.get("summary", "")

        if not profile:
            profile = ProposalProfile(
                user_id=user_id,
                title=title,
                event_type=event_type,
                filename=filename,
                file_path=file_path,
                full_text=text,
                target_audience=target_audience,
                expected_attendees=expected_attendees,
                location=location,
                event_date=event_date,
                requested_budget=requested_budget,
                sponsorship_tiers=tiers_json,
                detected_topics=topics_json,
                summary=summary,
                uploaded_at=datetime.now(timezone.utc).replace(tzinfo=None)
            )
            session.add(profile)
        else:
            profile.title = title
            profile.event_type = event_type
            profile.filename = filename
            profile.file_path = file_path
            profile.full_text = text
            profile.target_audience = target_audience
            profile.expected_attendees = expected_attendees
            profile.location = location
            profile.event_date = event_date
            profile.requested_budget = requested_budget
            profile.sponsorship_tiers = tiers_json
            profile.detected_topics = topics_json
            profile.summary = summary
            profile.uploaded_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await session.commit()
        await session.refresh(profile)
        logger.info(f"Proposal saved and profiled successfully for user {user_id}: '{title}'")
        return profile

    async def get_user_proposal(self, session: AsyncSession, user_id: int) -> Optional[ProposalProfile]:
        stmt = select(ProposalProfile).where(ProposalProfile.user_id == user_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

proposal_service = ProposalService()
