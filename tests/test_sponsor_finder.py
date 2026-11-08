import os
import pytest
import io
import docx
from sqlalchemy import select, func

from app.config.settings import settings
from app.database.db import init_db, async_session_maker
from app.database.models import Sponsor, ProposalProfile, AISponsorMatch, EmailQueue
from app.services.proposal_service import proposal_service
from app.agents.matching_agent import matching_agent
from app.agents.email_drafting_agent import email_drafting_agent
from app.agents import ALL_AGENTS

@pytest.mark.asyncio
async def test_database_and_seed():
    """Verify that database initializes and seeds corporate sponsors."""
    await init_db()
    async with async_session_maker() as session:
        res = await session.execute(select(func.count(Sponsor.id)))
        count = res.scalar_one()
        assert count > 0, "Sponsors catalog should be seeded with default companies"

@pytest.mark.asyncio
async def test_proposal_ingestion_and_profiling():
    """Verify proposal document parsing (.docx/.txt) and AI extraction."""
    user_id = 999888111
    
    # Create an in-memory docx proposal
    doc = docx.Document()
    doc.add_heading("HACKATHON NUSANTARA 2026 - NATIONAL STUDENT AI CHALLENGE", level=1)
    doc.add_paragraph("Target Audiens: 500 Mahasiswa Ilmu Komputer dan Rekayasa Perangkat Lunak seluruh Indonesia.")
    doc.add_paragraph("Tema: Artificial Intelligence, Cloud Computing, dan Solusi Dampak Sosial.")
    doc.add_paragraph("Paket Kemitraan: Platinum (Rp 30.000.000), Gold (Rp 15.000.000), In-Kind Tools & Cloud Credits.")
    doc.add_paragraph("Tanggal Pelaksanaan: 15-17 Oktober 2026 di Jakarta.")
    
    file_stream = io.BytesIO()
    doc.save(file_stream)
    doc_bytes = file_stream.getvalue()

    async with async_session_maker() as session:
        profile = await proposal_service.save_proposal(
            session=session,
            user_id=user_id,
            filename="Hackathon_Nusantara_Proposal.docx",
            file_bytes=doc_bytes
        )

        assert profile is not None
        assert profile.user_id == user_id
        assert "HACKATHON" in profile.full_text.upper()
        assert profile.file_path is not None
        assert os.path.exists(profile.file_path)

@pytest.mark.asyncio
async def test_matching_logic():
    """Verify AI matching engine scores sponsors based on proposal context."""
    user_id = 999888111
    matches = await matching_agent.match_sponsors_for_user(user_id=user_id)

    assert len(matches) > 0, "Matching agent should return recommended sponsors"
    top_match, sponsor = matches[0]
    assert top_match.score >= settings.SCORE_THRESHOLD
    assert top_match.recommended is True
    assert top_match.value_proposition_angle != ""

@pytest.mark.asyncio
async def test_email_drafting_with_attachment():
    """Verify that email drafting agent crafts a pitch and links proposal attachment."""
    user_id = 999888111
    async with async_session_maker() as session:
        # Get one sponsor
        s_res = await session.execute(select(Sponsor).where(Sponsor.contact_email != None).limit(1))
        sponsor = s_res.scalar_one_or_none()
        assert sponsor is not None

        draft = await email_drafting_agent.create_draft(
            session=session,
            user_id=user_id,
            sponsor_id=sponsor.id,
            suggested_tier="Gold Sponsor",
            pitch_angle="Akses langsung rekrutmen dan branding ke 500 mahasiswa teknik informatika."
        )

        assert draft is not None
        assert draft.status == "draft"
        assert draft.recipient_email == sponsor.contact_email
        assert draft.attachment_path is not None
        assert os.path.exists(draft.attachment_path)
        assert len(draft.body) > 50

def test_telemetry_status():
    """Verify all 8 agents expose healthy telemetry status."""
    assert len(ALL_AGENTS) == 8
    for agent in ALL_AGENTS:
        status = agent.get_status()
        assert "name" in status
        assert "feature" in status
        assert "status" in status
