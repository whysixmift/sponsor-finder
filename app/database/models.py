from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import String, Integer, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Sponsor(Base):
    """Corporate sponsors, brands, foundations, and venture funds."""
    __tablename__ = "sponsors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    partnership_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    region: Mapped[str] = mapped_column(String(50), default="Indonesia", index=True)  # "Indonesia", "Global"
    target_demographics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    typical_sponsorship: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sponsorship_guidelines: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_discovered: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(50), default="active")  # "active", "contacted", "blacklisted"
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    # Relationships
    opportunities: Mapped[List["SponsorOpportunity"]] = relationship(
        "SponsorOpportunity", back_populates="sponsor", cascade="all, delete-orphan"
    )
    matches: Mapped[List["AISponsorMatch"]] = relationship(
        "AISponsorMatch", back_populates="sponsor", cascade="all, delete-orphan"
    )
    emails: Mapped[List["EmailQueue"]] = relationship(
        "EmailQueue", back_populates="sponsor", cascade="all, delete-orphan"
    )
    favorites: Mapped[List["FavoriteSponsor"]] = relationship(
        "FavoriteSponsor", back_populates="sponsor", cascade="all, delete-orphan"
    )

class SponsorOpportunity(Base):
    """Specific active calls for proposals, grants, or recurring sponsorship tracks."""
    __tablename__ = "sponsor_opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    sponsor_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("sponsors.id", ondelete="CASCADE"), nullable=True)
    sponsor_name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100), index=True)
    region: Mapped[str] = mapped_column(String(50), default="Indonesia", index=True)
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    description: Mapped[str] = mapped_column(Text)
    benefits: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    sponsor: Mapped[Optional[Sponsor]] = relationship("Sponsor", back_populates="opportunities")

class ProposalProfile(Base):
    """Stores parsed event proposal document and extracted metadata."""
    __tablename__ = "proposal_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=0, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(100), default="General Event")
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    full_text: Mapped[str] = mapped_column(Text)
    target_audience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_attendees: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    event_date: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    requested_budget: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sponsorship_tiers: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    detected_topics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)     # JSON string
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

class AISponsorMatch(Base):
    """AI evaluation of proposal alignment with a specific sponsor."""
    __tablename__ = "ai_sponsor_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    proposal_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("proposal_profiles.id", ondelete="CASCADE"), nullable=True)
    sponsor_id: Mapped[int] = mapped_column(Integer, ForeignKey("sponsors.id", ondelete="CASCADE"))
    score: Mapped[int] = mapped_column(Integer, index=True)
    recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(Text)
    value_proposition_angle: Mapped[str] = mapped_column(Text)
    suggested_tier: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    matched_demographics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    priority: Mapped[Optional[str]] = mapped_column(String(50), default="medium")
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    sponsor: Mapped[Sponsor] = relationship("Sponsor", back_populates="matches")

    __table_args__ = (
        Index("ix_ai_matches_user_sponsor", "user_id", "sponsor_id", unique=True),
    )

class FavoriteSponsor(Base):
    """Bookmarked sponsors per user."""
    __tablename__ = "favorite_sponsors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    sponsor_id: Mapped[int] = mapped_column(Integer, ForeignKey("sponsors.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    sponsor: Mapped[Sponsor] = relationship("Sponsor", back_populates="favorites")

    __table_args__ = (
        Index("ix_favorites_user_sponsor", "user_id", "sponsor_id", unique=True),
    )

class History(Base):
    """System activity trail for user operations."""
    __tablename__ = "history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    action: Mapped[str] = mapped_column(String(50))
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

class EmailQueue(Base):
    """Sponsorship outreach draft and dispatch queue."""
    __tablename__ = "email_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    sponsor_id: Mapped[int] = mapped_column(Integer, ForeignKey("sponsors.id", ondelete="CASCADE"))
    recipient_email: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="draft")  # "draft", "approved", "rejected", "sending", "sent", "failed"
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="ai_pitch")
    attachment_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    sponsor: Mapped[Sponsor] = relationship("Sponsor", back_populates="emails")

class UserWhitelist(Base):
    """Permitted users for SaaS Bot and Web access."""
    __tablename__ = "user_whitelist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="approved")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

class UserGoogleAuth(Base):
    """Google OAuth2 credentials for sending emails directly via Gmail API."""
    __tablename__ = "user_google_auth"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255))
    access_token_encrypted: Mapped[str] = mapped_column(Text)
    refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    scopes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

class SMTPConfig(Base):
    """Encrypted SMTP configuration fallback."""
    __tablename__ = "smtp_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=0, unique=True, index=True)
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer)
    username: Mapped[str] = mapped_column(String(255))
    password_encrypted: Mapped[str] = mapped_column(Text)
    encryption_type: Mapped[str] = mapped_column(String(50))  # "SSL", "TLS", "None"
    sender_name: Mapped[str] = mapped_column(String(255))
    signature: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
