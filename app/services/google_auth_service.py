import os
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Optional, Tuple
import httpx
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.models import UserGoogleAuth
from app.services.email_service import encrypt_password, decrypt_password
from app.utils.logger import logger

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

class GoogleAuthService:
    def get_authorization_url(self, user_id: int) -> Optional[str]:
        if not settings.GOOGLE_CLIENT_ID:
            return None
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": f"{GMAIL_SEND_SCOPE} email profile",
            "access_type": "offline",
            "prompt": "consent",
            "state": str(user_id)
        }
        import urllib.parse
        return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def handle_oauth_callback(
        self,
        session: AsyncSession,
        code: str,
        user_id: int
    ) -> Tuple[bool, str]:
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            return False, "Google OAuth not configured in .env"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                data = {
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code"
                }
                res = await client.post(GOOGLE_TOKEN_URL, data=data)
                if res.status_code != 200:
                    return False, f"Token exchange failed: {res.text}"

                token_data = res.json()
                access_token = token_data.get("access_token")
                refresh_token = token_data.get("refresh_token")

                # Get user email
                userinfo_res = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                email = userinfo_res.json().get("email", f"user_{user_id}@gmail.com")

                # Save or update UserGoogleAuth
                stmt = select(UserGoogleAuth).where(UserGoogleAuth.user_id == user_id)
                res_db = await session.execute(stmt)
                auth_rec = res_db.scalar_one_or_none()

                if not auth_rec:
                    auth_rec = UserGoogleAuth(
                        user_id=user_id,
                        email=email,
                        access_token_encrypted=encrypt_password(access_token),
                        refresh_token_encrypted=encrypt_password(refresh_token) if refresh_token else None,
                        scopes=GMAIL_SEND_SCOPE,
                        is_active=True
                    )
                    session.add(auth_rec)
                else:
                    auth_rec.email = email
                    auth_rec.access_token_encrypted = encrypt_password(access_token)
                    if refresh_token:
                        auth_rec.refresh_token_encrypted = encrypt_password(refresh_token)
                    auth_rec.is_active = True
                    auth_rec.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

                await session.commit()
                return True, email

        except Exception as e:
            logger.error(f"Error handling Google OAuth callback: {e}")
            return False, str(e)

    async def refresh_access_token(self, session: AsyncSession, auth_record: UserGoogleAuth) -> Optional[str]:
        if not auth_record.refresh_token_encrypted:
            return None
        refresh_token = decrypt_password(auth_record.refresh_token_encrypted)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                data = {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token"
                }
                res = await client.post(GOOGLE_TOKEN_URL, data=data)
                if res.status_code == 200:
                    token_data = res.json()
                    new_access = token_data.get("access_token")
                    auth_record.access_token_encrypted = encrypt_password(new_access)
                    auth_record.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                    return new_access
        except Exception as e:
            logger.error(f"Error refreshing access token: {e}")
        return None

    async def send_email_via_gmail(
        self,
        session: AsyncSession,
        auth_record: UserGoogleAuth,
        to_email: str,
        subject: str,
        body: str,
        attachment_path: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Construct raw RFC 2822 message and POST to Gmail API messages/send."""
        access_token = decrypt_password(auth_record.access_token_encrypted)

        msg = MIMEMultipart()
        msg["From"] = auth_record.email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
            part["Content-Disposition"] = f'attachment; filename="{os.path.basename(attachment_path)}"'
            msg.attach(part)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

        url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=headers, json={"raw": raw})
            if resp.status_code == 401:
                # Token expired, try refreshing once
                new_token = await self.refresh_access_token(session, auth_record)
                if new_token:
                    headers["Authorization"] = f"Bearer {new_token}"
                    resp = await client.post(url, headers=headers, json={"raw": raw})

            if resp.status_code in [200, 201]:
                return True, None
            return False, f"Gmail API error {resp.status_code}: {resp.text}"

google_auth_service = GoogleAuthService()
