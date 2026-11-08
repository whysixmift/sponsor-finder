import os
import json
import smtplib
import asyncio
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import List, Optional, Tuple
from cryptography.fernet import Fernet
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import SMTPConfig, EmailQueue, UserGoogleAuth, ProposalProfile, Sponsor
from app.ai.evaluator import evaluator
from app.utils.logger import logger

SECRET_KEY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "secret.key"
)

def get_encryption_key() -> bytes:
    if os.path.exists(SECRET_KEY_PATH):
        try:
            with open(SECRET_KEY_PATH, "rb") as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"Error reading encryption key: {e}")

    try:
        os.makedirs(os.path.dirname(SECRET_KEY_PATH), exist_ok=True)
        key = Fernet.generate_key()
        with open(SECRET_KEY_PATH, "wb") as f:
            f.write(key)
        return key
    except Exception as e:
        logger.error(f"Failed to persist encryption key: {e}")
        return Fernet.generate_key()

CIPHER = Fernet(get_encryption_key())

def encrypt_password(password: str) -> str:
    return CIPHER.encrypt(password.encode("utf-8")).decode("utf-8")

def decrypt_password(encrypted: str) -> str:
    return CIPHER.decrypt(encrypted.encode("utf-8")).decode("utf-8")

class EmailService:
    async def configure_smtp(
        self,
        session: AsyncSession,
        user_id: int,
        host: str,
        port: int,
        username: str,
        password: str,
        encryption_type: str,
        sender_name: str,
        signature: str
    ) -> SMTPConfig:
        enc_type = encryption_type.upper()
        if enc_type not in ["SSL", "TLS", "NONE"]:
            raise ValueError("Encryption type must be SSL, TLS, or NONE")

        stmt = select(SMTPConfig).where(SMTPConfig.user_id == user_id)
        res = await session.execute(stmt)
        config = res.scalar_one_or_none()

        if not config:
            config = SMTPConfig(
                user_id=user_id,
                host=host,
                port=port,
                username=username,
                password_encrypted=encrypt_password(password),
                encryption_type=enc_type,
                sender_name=sender_name,
                signature=signature,
                is_active=True
            )
            session.add(config)
        else:
            config.host = host
            config.port = port
            config.username = username
            config.password_encrypted = encrypt_password(password)
            config.encryption_type = enc_type
            config.sender_name = sender_name
            config.signature = signature
            config.is_active = True

        await session.commit()
        await session.refresh(config)
        return config

    async def get_active_smtp_config(self, session: AsyncSession, user_id: int) -> Optional[SMTPConfig]:
        stmt = select(SMTPConfig).where(and_(SMTPConfig.user_id == user_id, SMTPConfig.is_active == True))
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def draft_sponsorship_email(
        self,
        session: AsyncSession,
        user_id: int,
        sponsor_id: int,
        suggested_tier: Optional[str] = None,
        pitch_angle: Optional[str] = None
    ) -> EmailQueue:
        """Create personalized cold sponsorship outreach draft with attached proposal."""
        # 1. Fetch Sponsor
        sponsor_stmt = select(Sponsor).where(Sponsor.id == sponsor_id)
        res = await session.execute(sponsor_stmt)
        sponsor = res.scalar_one_or_none()
        if not sponsor:
            raise ValueError(f"Sponsor #{sponsor_id} not found")

        recipient_email = sponsor.contact_email
        if not recipient_email:
            raise ValueError(f"Sponsor '{sponsor.name}' does not have a registered contact email yet.")

        # 2. Fetch User's Proposal
        prop_stmt = select(ProposalProfile).where(ProposalProfile.user_id == user_id)
        res_prop = await session.execute(prop_stmt)
        proposal = res_prop.scalar_one_or_none()

        title = proposal.title if proposal else "Event Collaboration"
        summary = proposal.summary if proposal else "Exciting community event"
        event_date = proposal.event_date if proposal else "Upcoming"
        attachment_path = proposal.file_path if proposal else None

        # 3. AI Drafting
        subject, body = await evaluator.write_sponsorship_pitch(
            sponsor_name=sponsor.name,
            contact_person=None,
            proposal_title=title,
            proposal_summary=summary,
            suggested_tier=suggested_tier,
            pitch_angle=pitch_angle or "Membuka peluang kemitraan bernilai tinggi dengan audiens tersegmen.",
            event_date=event_date
        )

        # 4. Save to EmailQueue
        email_record = EmailQueue(
            user_id=user_id,
            sponsor_id=sponsor_id,
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            status="draft",
            source="ai_pitch",
            attachment_path=attachment_path,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        session.add(email_record)
        await session.commit()
        await session.refresh(email_record)
        logger.info(f"Drafted sponsorship email to {sponsor.name} ({recipient_email}) for user {user_id}")
        return email_record

    async def dispatch_email(self, session: AsyncSession, email_id: int) -> bool:
        """Dispatch email using Gmail API (if connected) or SMTP fallback."""
        stmt = select(EmailQueue).where(EmailQueue.id == email_id)
        res = await session.execute(stmt)
        email_record = res.scalar_one_or_none()

        if not email_record:
            raise ValueError(f"Email #{email_id} not found")

        user_id = email_record.user_id

        # 1. Check Google OAuth credentials
        google_stmt = select(UserGoogleAuth).where(and_(UserGoogleAuth.user_id == user_id, UserGoogleAuth.is_active == True))
        google_res = await session.execute(google_stmt)
        google_auth = google_res.scalar_one_or_none()

        if google_auth:
            from app.services.google_auth_service import google_auth_service
            success, err = await google_auth_service.send_email_via_gmail(
                session=session,
                auth_record=google_auth,
                to_email=email_record.recipient_email,
                subject=email_record.subject,
                body=email_record.body,
                attachment_path=email_record.attachment_path
            )
            if success:
                email_record.status = "sent"
                email_record.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
                await session.commit()
                return True
            else:
                logger.warning(f"Gmail API dispatch failed, falling back to SMTP: {err}")

        # 2. Fallback to SMTP
        smtp_conf = await self.get_active_smtp_config(session, user_id)
        if not smtp_conf:
            email_record.status = "failed"
            email_record.error_message = "No active Gmail OAuth or SMTP credentials configured."
            await session.commit()
            raise ValueError("No active Gmail or SMTP credentials found. Please configure SMTP or connect Google account.")

        try:
            # Build MIME message
            msg = MIMEMultipart()
            msg["From"] = f"{smtp_conf.sender_name} <{smtp_conf.username}>"
            msg["To"] = email_record.recipient_email
            msg["Subject"] = email_record.subject

            full_body = f"{email_record.body}\n\n{smtp_conf.signature or ''}".strip()
            msg.attach(MIMEText(full_body, "plain", "utf-8"))

            if email_record.attachment_path and os.path.exists(email_record.attachment_path):
                with open(email_record.attachment_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(email_record.attachment_path))
                part["Content-Disposition"] = f'attachment; filename="{os.path.basename(email_record.attachment_path)}"'
                msg.attach(part)

            # Send via smtplib
            password = decrypt_password(smtp_conf.password_encrypted)
            loop = asyncio.get_running_loop()

            def _send_smtp():
                if smtp_conf.encryption_type == "SSL":
                    context = ssl.create_default_context()
                    with smtplib.SMTP_SSL(smtp_conf.host, smtp_conf.port, context=context, timeout=15) as s:
                        s.login(smtp_conf.username, password)
                        s.send_message(msg)
                else:
                    with smtplib.SMTP(smtp_conf.host, smtp_conf.port, timeout=15) as s:
                        if smtp_conf.encryption_type == "TLS":
                            s.starttls(context=ssl.create_default_context())
                        s.login(smtp_conf.username, password)
                        s.send_message(msg)

            await loop.run_in_executor(None, _send_smtp)

            email_record.status = "sent"
            email_record.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
            email_record.error_message = None
            await session.commit()
            return True

        except Exception as e:
            logger.error(f"SMTP dispatch failed: {e}")
            email_record.status = "failed"
            email_record.error_message = str(e)
            await session.commit()
            raise e

email_service = EmailService()
