import logging

from src.db.model import User, GoogleAccount, OAuthSession
from sqlmodel import select
from sqlalchemy.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


class GoogleService:
    async def create_gmail_user(self, data: dict, session: AsyncSession):
        """Create or update a connected Gmail account."""

        existing = await self.get_gmail_user_by_id(str(data.get("user_uid")), session)
        if existing:
            existing.access_token = data["access_token"]
            existing.refresh_token = data.get("refresh_token") or existing.refresh_token
            existing.token_expiry = data.get("token_expiry")
            existing.scope = data.get("scope", existing.scope)
            existing.google_email = data.get("google_email", existing.google_email)
            await session.commit()
            return existing

        new_user = GoogleAccount(**data)
        session.add(new_user)
        await session.commit()
        return new_user

    async def get_gmail_user_by_email(self, email: str, session: AsyncSession):
        stmt = select(GoogleAccount).where(GoogleAccount.google_email == email)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def get_gmail_user_by_id(self, id: str, session: AsyncSession):
        import uuid
        try:
            uuid_id = uuid.UUID(id) if isinstance(id, str) else id
        except ValueError:
            uuid_id = id
        stmt = select(GoogleAccount).where(GoogleAccount.user_uid == uuid_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def get_code_verifier_state(self, state: str, session: AsyncSession):
        stmt = select(OAuthSession).where(OAuthSession.state == state)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def create_oauth_session(
        self, user_uid: str, state: str, code_verifier: str, session: AsyncSession
    ):
        new_session = OAuthSession(
            user_uid=user_uid, state=state, code_verifier=code_verifier
        )
        session.add(new_session)
        await session.commit()
        return new_session